import gc
import pdfplumber
import pandas as pd
import re
import io
import json
import os
import time
import functools
from datetime import datetime, timedelta
from collections import defaultdict
from google import genai
from google.genai import types
from meritz_easy_rules import evaluate_meritz_easy

# ==========================================
# 키워드 로딩 (keywords.json 외부화)
# ==========================================
_KW_PATH = os.path.join(os.path.dirname(__file__), "keywords.json")

def _load_keywords():
    with open(_KW_PATH, encoding="utf-8") as f:
        return json.load(f)

_KW = _load_keywords()

surg_keywords          = _KW["surg_keywords"]
surg_negative_keywords = _KW["surg_negative_keywords"]
test_keywords          = _KW["test_keywords"]
nhis_surg_keywords     = _KW["nhis_surg_keywords"]
SIMPLE_Q3_CODES            = tuple(_KW["simple_q3_codes"])
HEALTH_Q5_CODES            = tuple(_KW["health_q5_codes"])
SIMPLE_Q3_ALLOWED_PREFIXES = tuple(_KW["simple_q3_allowed_prefixes"])
_FTYPE_KW                  = _KW["detect_file_type_keywords"]

# ==========================================
# 헬퍼 함수
# ==========================================

def get_val(row, possible_keys):
    for k in row.keys():
        if any(pk in str(k) for pk in possible_keys):
            val = row[k]
            return str(val).strip() if pd.notna(val) else ""
    return ""


def normalize_code(raw: str | None) -> str:
    if raw is None:
        return ""
    code = str(raw).strip()
    if not code:
        return ""
    code = code.upper()
    if not code or code == "$":
        return ""
    # 점/하이픈/공백 제거 (O33.9 → O339)
    code = code.replace(".", "").replace("-", "").replace(" ", "")
    # 첫 글자 A/B + 두번째도 영문 = 양방/한의학 구분자 → 첫 글자만 제거
    # (예: AK635→K635, BM179→M179, AE1150→E1150)
    # 단, B20(에이즈), A09(감염) 등 실제 코드는 유지
    if len(code) >= 3 and code[0] in ("A", "B") and code[1].isalpha():
        code = code[1:]
    # 이제 코드는 [영문대분류][숫자...] 형태여야 함 (예: O339, I639, E115)
    # 대분류 알파벳 뒤 선행 0 제거 (O0339 → O339)
    if len(code) >= 2 and code[0].isalpha() and len(code) > 1:
        alpha = code[0]
        digits = code[1:]
        digits = digits.lstrip("0") or "0"
        # 상병코드는 대분류 + 2~4자리 숫자 (예: O339, I6390)
        # 원래 코드가 3자리 이상이어야 유효
        if len(digits) >= 2:
            code = alpha + digits
    # OCR "1" → "I" 보정 (숫자로 시작하면 I로 교정)
    if code and code[0] == "1" and len(code) >= 3:
        candidate = "I" + code[1:]
        if candidate[1:3].isdigit():
            code = candidate
    return code


def parse_date(date_str: str) -> str:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if m:
        return m.group()
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{8})", date_str)
    if m:
        d = m.group()
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return ""


def row_is_junk(row) -> bool:
    combined = "".join(str(v) for v in row.values).replace(" ", "")
    return "$" in combined or "해당없음" in combined


@functools.lru_cache(maxsize=512)
def detect_file_type(headers):
    h_joined = " ".join(str(h) for h in headers)
    h_norm = h_joined.replace(" ", "").replace("\n", "")

    # 1차: 키워드 사전 (keywords.json 외부화)
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["basic"]):
        return "basic"
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["detail"]):
        return "detail"
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["pharma"]):
        return "pharma"

    # 2차: 행 데이터 패턴 기반 추론 (컬럼 수, 날짜/코드 패턴)
    n_cols = len(headers)
    has_date_col = any(re.search(r"일$|날짜|일자|개시", str(h)) for h in headers)
    has_code_like = any(re.search(r"코드|기호|분류", str(h)) for h in headers)
    has_drug_like = any(re.search(r"약|처방|조제|투약", str(h)) for h in headers)
    has_act_like = any(re.search(r"행위|내역|명칭|처치|급여", str(h)) for h in headers)

    if has_drug_like:
        return "pharma"
    if has_act_like and n_cols >= 5:
        return "detail"
    if has_date_col and has_code_like:
        return "basic"

    return "unknown"


def _is_surgery_match(text: str) -> bool:
    """수술 키워드 매칭 — positive + negative 동시 적용"""
    if not text:
        return False
    has_positive = any(kw in text for kw in surg_keywords)
    if not has_positive:
        return False
    has_negative = any(kw in text for kw in surg_negative_keywords)
    if has_negative:
        # negative가 있어도 강력한 수술 키워드면 통과
        strong_surg = ["수술", "절제", "절개", "적출", "봉합", "이식", "절단", "재건", "치환", "관혈", "배농"]
        return any(kw in text for kw in strong_surg)
    return True


def _to_int_cost(raw: str) -> int:
    """진료비 문자열에서 정수 비용 추출 (예: '1,234,500원' -> 1234500)."""
    if not raw:
        return 0
    nums = re.findall(r"\d+", str(raw))
    if not nums:
        return 0
    try:
        return int("".join(nums))
    except Exception:
        return 0


def _cross_key(code_str: str, name_str: str) -> str:
    """기본/세부/처방을 같은 질병 단위로 맞추기 위한 키."""
    if code_str:
        return code_str
    return re.sub(r"[\s\d\.\-_/]", "", name_str or "")[:18]


def parse_nhis_text(text, fname):
    """건강보험 요양급여내역 텍스트에서 진료 레코드 파싱"""
    records = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    date_re  = re.compile(r'^(\d{4}\.\d{2}\.\d{2})\s+\d+\s+(.+?)\s+\d{2,4}-\d{3,4}-\d{4}')
    visit_re = re.compile(r'^(외래|입원|약국)\s+(\d+)\s*(.*)')
    seq_re   = re.compile(r'^\d+$')
    cur_date, cur_hospital = None, None
    i = 0
    while i < len(lines):
        line = lines[i]
        m_d = date_re.match(line)
        if m_d:
            cur_date     = m_d.group(1)
            cur_hospital = m_d.group(2).strip()
            i += 1
            continue
        if seq_re.match(line) and cur_date:
            i += 1
            if i < len(lines):
                m_v = visit_re.match(lines[i])
                if m_v:
                    in_out_v = m_v.group(1)
                    if in_out_v == "약국":
                        i += 1
                        continue
                    days_v = m_v.group(2)
                    rest   = m_v.group(3).strip()
                    parts  = rest.split()
                    code_v = ""
                    name_v = ""
                    for pi, p in enumerate(parts):
                        if re.match(r'^[A-Z]\d', p):
                            code_v = p
                            name_v = " ".join(parts[:pi])
                            break
                    if not name_v and not code_v:
                        name_v = rest
                    if name_v or code_v:
                        records.append({
                            "진료개시일": cur_date,
                            "요양기관명": cur_hospital or "",
                            "입내원구분": in_out_v,
                            "요양일수":   days_v,
                            "상병명":     name_v,
                            "상병코드":   code_v,
                            "_ftype":     "nhis",
                            "_fname":     fname,
                        })
                i += 1
            continue
        i += 1
    return records


def _open_pdf(data, bdate_str):
    """비밀번호 없이 시도 후 실패하면 생년월일 조합으로 재시도"""
    bd = (bdate_str or "").strip()
    bd_digits = re.sub(r"\D", "", bd)
    candidates = [""]
    if bd:
        candidates.append(bd)
    if bd_digits and bd_digits != bd:
        candidates.append(bd_digits)
    if len(bd_digits) == 8:
        candidates.append(bd_digits[2:])
    elif len(bd_digits) == 6:
        yy = int(bd_digits[:2])
        prefix = "20" if yy <= 24 else "19"
        candidates.append(prefix + bd_digits)
    # 시도 순서 유지하며 중복 제거
    candidates = list(dict.fromkeys(candidates))
    for pw in candidates:
        try:
            return pdfplumber.open(io.BytesIO(data), password=pw)
        except Exception:
            continue
    raise ValueError("PDF 비밀번호 해제 실패 — 생년월일을 확인해 주세요.")


_DRUG_SUFFIX_RE = re.compile(
    r'(정|캡슐|캡|앰플|바이알|시럽|액|필름코팅정|서방정|장용정|현탁액|연질캡슐'
    r'|구강붕해정|설하정|츄어블정|패치|주사|크림|겔|연고|점안액|점비액)\s*$',
    flags=re.IGNORECASE
)
_DRUG_PAREN_RE = re.compile(r'\([^)]*\)')
_DRUG_MAKER_RE = re.compile(
    r'(한미|대웅|유한|종근당|동아|일동|보령|녹십자|삼성|JW|CJ|GSK|화이자|노바티스'
    r'|아스트라제네카|사노피|MSD|릴리|바이엘|로슈|한국|제일|경동|환인|명인|광동'
    r'|HK|SK|LG|셀트리온|삼진|국제|영진|안국|태극|코오롱|대원|신풍|동국)\s*제약?\s*',
    flags=re.IGNORECASE
)
_DOSE_UNIT_TO_MG = {"mg": 1.0, "g": 1000.0, "mcg": 0.001, "ug": 0.001, "iu": 0.001, "ml": 1.0}


@functools.lru_cache(maxsize=1024)
def extract_drug_info(name: str):
    """(정규화된 성분명, 용량_mg) 튜플 반환. 용량 없으면 0"""
    # 용량 추출 및 mg 단위 환산
    dose_match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|ml|g|ug|IU)', name, flags=re.IGNORECASE)
    if dose_match:
        raw_dose = float(dose_match.group(1))
        unit = dose_match.group(2).lower()
        dose = raw_dose * _DOSE_UNIT_TO_MG.get(unit, 1.0)
    else:
        dose = 0.0

    # 성분명 정규화: 숫자+단위 제거 → 괄호 제거 → 제형 suffix 제거 → 제조사 제거
    base = re.sub(r'\d+(\.\d+)?\s*(mg|mcg|ml|g|ug|IU)', '', name, flags=re.IGNORECASE)
    base = _DRUG_PAREN_RE.sub('', base)
    base = _DRUG_SUFFIX_RE.sub('', base)
    base = _DRUG_MAKER_RE.sub('', base)
    # 공백/특수문자 정리 후 소문자 표준화
    base = re.sub(r'[\s\-_/·]+', '', base).lower().strip()
    return base, dose


@functools.lru_cache(maxsize=256)
def extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 추출 — 여러 방법 시도"""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end])
        except Exception:
            pass
    lines = cleaned.split("\n")
    json_lines = []
    in_json = False
    brace_count = 0
    for line in lines:
        if not in_json and line.strip().startswith("{"):
            in_json = True
        if in_json:
            json_lines.append(line)
            brace_count += line.count("{") - line.count("}")
            if brace_count <= 0 and json_lines:
                break
    if json_lines:
        try:
            return json.loads("\n".join(json_lines))
        except Exception:
            pass
    raise ValueError(f"JSON 추출 실패. 원문 앞 200자: {text[:200]}")


def _make_merged_item(item: dict, q: str, code_override: str = "") -> dict:
    return {
        "dates":          [item.get("date", "")],
        "code":           code_override or item.get("code", "-"),
        "name":           item.get("disease", ""),
        "duty_question":  q,
        "reason":         item.get("reason", ""),
        "is_inpatient":   item.get("is_inpatient", False),
        "inpatient_days": item.get("inpatient_days", 0),
        "inpatient_count": item.get("inpatient_count", 0),
        "visit_count":    item.get("visit_count", 0),
        "first_diagnosis_date": item.get("first_diagnosis_date", ""),
        "is_surgery":     item.get("is_surgery", False),
        "surgery_name":   item.get("surgery_name"),
        "surgery_dates":  [item.get("date", "")] if item.get("is_surgery") else [],
        "med_days":       item.get("med_days", 0),
        "weight":         item.get("weight", "mid"),
        "hospitals":      [item.get("hospital", "")],
    }


def new_disease():
    return {
        "visit_dates": set(), "med_dates_basic": {}, "med_dates_pharma": {},
        "drug_names_in_90": set(), "drug_names_before_90": set(),
        "tests_found": set(), "inpatient_dates": set(),
        "surgeries": set(), "surgery_dates": set(), "hospitals": set(),
        "_daily_facts": {},
        "_inpatient_days_map": {},   # date → max(내원일수) per inpatient record
        "first_date": "2099-12-31", "latest_date": "2000-01-01",
        "diag_code": "", "name": "", "has_pharma": False,
    }


def _code_in(code, prefixes):
    if code is None:
        return False
    c = str(code).strip()
    if not c:
        return False
    c = c.upper()
    return any(c.startswith(p) for p in prefixes)


def _dts_in_range(date_set, since_dt):
    result = []
    for d in date_set:
        try:
            if d and datetime.strptime(d, "%Y-%m-%d") >= since_dt:
                result.append(d)
        except ValueError:
            pass
    return sorted(result)


def _parse_ymd(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def _max_presc(med_dict, since_dt):
    return max(
        (v for d, v in med_dict.items()
         if d and datetime.strptime(d, "%Y-%m-%d") >= since_dt),
        default=0,
    ) if med_dict else 0


def is_simple_q3_allowed(code: str) -> bool:
    """간편심사 Q3 허용 코드인지 확인"""
    if code is None:
        return False
    code = str(code).strip()
    if not code:
        return False
    code = code.upper()
    for prefix in SIMPLE_Q3_ALLOWED_PREFIXES:
        if code.startswith(prefix):
            return True
    return False


# ==========================================
# 예외 클래스
# ==========================================
class AnalysisError(Exception):
    def __init__(self, message, raw_response=None):
        super().__init__(message)
        self.raw_response = raw_response


# ==========================================
# 분석 엔진
# ==========================================
def run_analysis(active_files, product_type, reference_date, birthdate_pw, api_key) -> dict:
    """
    PDF 파일들을 분석하여 알릴의무 항목을 추출합니다.

    Returns dict with keys:
        ai_result, summary_reports, flagged_codes,
        prescription_end_details, drug_change_summary,
        analysis_today, parse_errors, retry_warnings

    Raises:
        AnalysisError: 분석 실패 시
    """
    today = datetime(reference_date.year, reference_date.month, reference_date.day)
    all_records = []
    parse_errors = []
    retry_warnings = []

    # ── PDF 파싱 ──────────────────────────────────────────────────
    for uploaded_file in active_files:
        file_recs = []
        pdf_data = uploaded_file.read()
        try:
            with _open_pdf(pdf_data, birthdate_pw or "") as pdf:
                first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
                is_nhis = "건강보험 요양급여내역" in first_text

                if is_nhis:
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        if "건강보험 요양급여내역" in page_text:
                            recs = parse_nhis_text(page_text, uploaded_file.name)
                            file_recs.extend(recs)
                            all_records.extend(recs)
                        del page_text
                else:
                    for page in pdf.pages:
                        tables = page.extract_tables()
                        for table in tables:
                            if not table or len(table) < 2:
                                continue
                            raw_headers = table[0]
                            headers = [
                                str(h).replace("\n", "").replace(" ", "") if h else f"col_{i}"
                                for i, h in enumerate(raw_headers)
                            ]
                            ftype = detect_file_type(tuple(headers))
                            for row in table[1:]:
                                if not any(row):
                                    continue
                                if "순번" in str(row[0]):
                                    continue
                                rec = {h: str(v).replace("\n", " ").strip() if v else "" for h, v in zip(headers, row)}
                                rec["_ftype"] = ftype
                                rec["_fname"] = uploaded_file.name
                                all_records.append(rec)
                                file_recs.append(rec)
                        del tables
        except ValueError as e:
            parse_errors.append(f"🔒 {uploaded_file.name}: {e}")
            continue
        except Exception as e:
            err_str = str(e)
            if "password" in err_str.lower() or "encrypted" in err_str.lower():
                parse_errors.append(f"🔒 {uploaded_file.name}: 비밀번호가 걸린 PDF입니다. 생년월일을 입력해 주세요.")
            elif "pdf" in err_str.lower() or "syntax" in err_str.lower():
                parse_errors.append(f"⚠️ {uploaded_file.name}: 손상되었거나 지원하지 않는 PDF 형식입니다.")
            else:
                parse_errors.append(f"⚠️ {uploaded_file.name}: 파일 읽기 실패 — {err_str[:80]}")
            continue
        finally:
            del pdf_data, file_recs
            gc.collect()

    if not all_records:
        raise AnalysisError("PDF에서 데이터를 추출하지 못했습니다. 파일 형식이나 비밀번호를 확인해 주세요.")

    df = pd.DataFrame(all_records)
    disease_stats = defaultdict(new_disease)

    # ── 날짜 파싱 실패/미래일자 추적 ────────────────────────────
    date_parse_fail_count = 0
    date_parse_fail_samples = []
    future_date_count = 0

    # ── disease_stats 구축 ────────────────────────────────────────
    # 동일 날짜/동일 코드 기준 교차검증용 인덱스
    # key: (cross_code_or_name, YYYY-MM-DD)
    cross_day_index = defaultdict(lambda: {
        "max_basic_cost": 0,
        "basic_hospitals": set(),
        "detail_proc_names": set(),
        "has_detail_surg_kw": False,
        "inpatient_flag": False,
    })

    for _, row in df.iterrows():
        if row_is_junk(row):
            continue
        ftype    = str(row.get("_ftype", "unknown"))
        dept     = get_val(row, ["진단과"])
        # 기본진료내역에서 '진단과: 일반의'는 약국 처방성 데이터로 간주 → 전체 분석에서 제외
        if ftype in ("basic", "unknown") and dept.replace(" ", "") == "일반의":
            continue
        # 처방조제(pharma)의 코드는 약품/분류코드일 수 있어 질병코드 판정에서 제외
        raw_code = "" if ftype == "pharma" else get_val(row, ["코드", "상병코드", "진단코드"])
        code_str = normalize_code(raw_code)
        name_str = get_val(row, ["상병명", "약품명", "진료내역", "행위명", "처치및수술", "처치및수 술"])
        in_out   = get_val(row, ["입내원구분", "입원외래구분", "입원", "외래", "구분"])
        hospital = get_val(row, ["병·의원", "기관명", "요양기관명"])
        date_str = get_val(row, ["진료개시일", "진료시작일", "진료일", "조제일자", "처방일"])
        m_days_raw = get_val(row, ["내원일수", "투약일수", "요양일수"])
        m_days = int(re.findall(r"\d+", m_days_raw)[0]) if re.findall(r"\d+", m_days_raw) else 0
        cost_raw = get_val(row, ["총진료비", "진료비", "총 진료비", "본인부담총액", "급여비용총액"])
        cost_val = _to_int_cost(cost_raw)

        if code_str:
            group_key = code_str
        else:
            # 코드 없는 경우: 이름 정규화 + 병원 + 월 조합으로 충돌 방지
            name_norm = re.sub(r"[\s\d\.\-]", "", name_str)[:12]
            month_bucket = parse_date(date_str)[:7] if parse_date(date_str) else ""
            hosp_short = hospital[:6] if hospital else ""
            group_key = f"{name_norm}|{hosp_short}|{month_bucket}" if name_norm else ""
        if not group_key:
            continue

        clean_date = parse_date(date_str)
        if date_str and not clean_date:
            date_parse_fail_count += 1
            if len(date_parse_fail_samples) < 5:
                date_parse_fail_samples.append(date_str[:30])

        s = disease_stats[group_key]

        if code_str and not s["diag_code"]:
            s["diag_code"] = code_str

        if clean_date:
            dt = datetime.strptime(clean_date, "%Y-%m-%d")
            days_ago = (today - dt).days

            # 미래 날짜 제외 (OCR 오류 가능)
            if days_ago < 0:
                future_date_count += 1
                continue

            if ftype in ("basic", "unknown"):
                is_inpatient = "입원" in in_out or "입원" in name_str
                if is_inpatient:
                    s["inpatient_dates"].add(clean_date)
                    if m_days > 0:
                        prev_inp = s["_inpatient_days_map"].get(clean_date, 0)
                        s["_inpatient_days_map"][clean_date] = max(prev_inp, m_days)
                else:
                    s["visit_dates"].add(clean_date)
                if m_days > 0:
                    prev = s["med_dates_basic"].get(clean_date, 0)
                    if m_days > prev:
                        s["med_dates_basic"][clean_date] = m_days
                # 동일일자 교차검증용 기본진료 정보(병원비/입원) 저장
                day_fact = s["_daily_facts"].setdefault(clean_date, {"max_basic_cost": 0, "detail_proc_names": set()})
                day_fact["max_basic_cost"] = max(day_fact["max_basic_cost"], cost_val)
            elif ftype == "detail":
                act_name = get_val(row, ["행위명칭", "행위명", "진료내역", "처치"])
                # ★ "처치및수술" 컬럼 구분값이 존재하면 키워드 무관하게 수술 확정
                surg_col = get_val(row, ["처치및수술", "처치및수 술", "처치/수술"])
                surg_target = act_name if act_name else name_str
                is_surg_by_column = bool(surg_col and surg_col.strip() and surg_col.strip() != "0")
                is_surg_by_keyword = _is_surgery_match(surg_target)

                if is_surg_by_column:
                    # 세부진료 "처치및수술" 컬럼에 값이 있음 = 확정 수술
                    surg_label = surg_col.strip() if len(surg_col.strip()) > 2 else (surg_target or "처치및수술")
                    s["surgeries"].add(surg_label)
                    s["surgery_dates"].add(clean_date)
                elif is_surg_by_keyword:
                    s["surgeries"].add(surg_target)
                    s["surgery_dates"].add(clean_date)

                day_fact = s["_daily_facts"].setdefault(clean_date, {"max_basic_cost": 0, "detail_proc_names": set()})
                if surg_target:
                    day_fact["detail_proc_names"].add(surg_target)
                day_fact["_is_surg_by_column"] = day_fact.get("_is_surg_by_column", False) or is_surg_by_column
                for kw in test_keywords:
                    if kw in surg_target:
                        s["tests_found"].add(surg_target); break
            elif ftype == "pharma":
                s["has_pharma"] = True
                if m_days > 0:
                    prev = s["med_dates_pharma"].get(clean_date, 0)
                    if m_days > prev:
                        s["med_dates_pharma"][clean_date] = m_days
                drug = name_str.strip()
                if drug:
                    if days_ago <= 90: s["drug_names_in_90"].add(drug)
                    else: s["drug_names_before_90"].add(drug)
            elif ftype == "nhis":
                if in_out == "입원":
                    s["inpatient_dates"].add(clean_date)
                    if m_days > 0:
                        prev_inp = s["_inpatient_days_map"].get(clean_date, 0)
                        s["_inpatient_days_map"][clean_date] = max(prev_inp, m_days)
                elif in_out == "약국":
                    s["has_pharma"] = True
                else:
                    s["visit_dates"].add(clean_date)
                # nhis는 강한 수술 키워드 사용 (nhis_surg_keywords는 의료수가 코드 기반이라 오탐 낮음)
                if _is_surgery_match(name_str) or any(kw in name_str for kw in nhis_surg_keywords):
                    s["surgeries"].add(name_str)
                    if clean_date: s["surgery_dates"].add(clean_date)
                for kw in test_keywords:
                    if kw in name_str: s["tests_found"].add(name_str); break

            if ftype in ("basic", "unknown"):
                if _is_surgery_match(name_str):
                    s["surgeries"].add(name_str)
                    if clean_date: s["surgery_dates"].add(clean_date)
                for kw in test_keywords:
                    if kw in name_str: s["tests_found"].add(name_str); break

            if clean_date > s["latest_date"]: s["latest_date"] = clean_date
            if clean_date < s["first_date"]:  s["first_date"]  = clean_date

            # 전역 동일일자 인덱스 업데이트 (기본/세부 파일 교차확인)
            ckey = _cross_key(code_str, name_str)
            if ckey:
                idx = cross_day_index[(ckey, clean_date)]
                if ftype in ("basic", "unknown"):
                    idx["max_basic_cost"] = max(idx["max_basic_cost"], cost_val)
                    if hospital:
                        idx["basic_hospitals"].add(hospital)
                    if "입원" in in_out or "입원" in name_str:
                        idx["inpatient_flag"] = True
                elif ftype == "detail":
                    act_name_idx = get_val(row, ["행위명칭", "행위명", "진료내역", "처치", "처치및수술", "처치및수 술"])
                    target_idx = act_name_idx if act_name_idx else name_str
                    if target_idx:
                        idx["detail_proc_names"].add(target_idx)
                    if _is_surgery_match(target_idx):
                        idx["has_detail_surg_kw"] = True

        if hospital and "약국" not in hospital and ftype != "pharma":
            s["hospitals"].add(hospital)
        if name_str and not s["name"]:
            s["name"] = name_str

    # ── 기본진료+세부진료 동일일자 교차 수술 추정 ────────────────
    # 규칙 기반 확정: 세부진료 "처치및수술" 컬럼 값 OR (수술키워드 + 고비용)
    # 규칙으로 불가능한 애매 케이스: AI에 근거(비용+행위명) 전달
    HIGH_SURGERY_COST = 300000
    MEDIUM_SURGERY_COST = 150000
    cross_surgery_hints = []
    for _ck, _s in disease_stats.items():
        _dc = (_s.get("diag_code") or "").strip()
        _name = _s.get("name", "")
        ckey = _cross_key(_dc, _name) if (_dc or _name) else ""
        if not ckey:
            continue
        for d, day_fact in _s.get("_daily_facts", {}).items():
            idx = cross_day_index.get((ckey, d))
            if not idx:
                continue
            max_cost = idx.get("max_basic_cost", 0)
            has_detail_proc = bool(idx.get("detail_proc_names"))
            has_detail_surg_kw = bool(idx.get("has_detail_surg_kw"))
            # ★ 세부진료 "처치및수술" 컬럼으로 확정된 경우 — 비용 무관 수술 확정
            is_col_confirmed = day_fact.get("_is_surg_by_column", False)

            if is_col_confirmed:
                # 세부진료 컬럼값으로 이미 수술 확정 — 교차확인 기록만
                if d not in _s["surgery_dates"]:
                    _s["surgery_dates"].add(d)
                    if idx["detail_proc_names"]:
                        _s["surgeries"].update(idx["detail_proc_names"])
                cross_surgery_hints.append(
                    f"{d} {_dc or ckey} {'|'.join(list(idx.get('detail_proc_names', set()))[:2]) or _name} "
                    f"컬럼확정(처치및수술+기본진료비 {max_cost:,}원)"
                )
            elif has_detail_proc and max_cost >= HIGH_SURGERY_COST:
                # 세부진료 행위명 + 기본진료 고비용 → 수술 확정
                if d not in _s["surgery_dates"]:
                    _s["surgery_dates"].add(d)
                if idx["detail_proc_names"]:
                    _s["surgeries"].update(idx["detail_proc_names"])
                    _hint_name = next(iter(idx["detail_proc_names"]))
                else:
                    _hint_name = _name or _dc or "수술"
                cross_surgery_hints.append(
                    f"{d} {_dc or ckey} {_hint_name} 교차확정(세부처치+기본진료비 {max_cost:,}원)"
                )
            elif has_detail_surg_kw and max_cost >= MEDIUM_SURGERY_COST:
                # 수술 키워드 + 중간 비용 → AI에 힌트 전달 (규칙으로 확정 불가)
                _hint_name = next(iter(idx["detail_proc_names"])) if idx["detail_proc_names"] else (_name or _dc or "진료")
                cross_surgery_hints.append(
                    f"{d} {_dc or ckey} {_hint_name} 교차후보(수술키워드+기본진료비 {max_cost:,}원) ★AI판단필요"
                )

    # ── 날짜 파싱 실패/미래일자 경고 ─────────────────────────────
    if date_parse_fail_count > 0:
        sample_text = ", ".join(date_parse_fail_samples[:3])
        parse_errors.append(
            f"⚠️ 날짜 인식 실패 {date_parse_fail_count}건 (예: {sample_text}) — "
            f"해당 레코드의 기간 판정이 누락될 수 있습니다."
        )
    if future_date_count > 0:
        parse_errors.append(
            f"⚠️ 미래 날짜 {future_date_count}건 감지 (OCR 오류 가능) — 해당 레코드를 제외했습니다."
        )

    # ── 코드 기반 결정론적 알릴의무 ──────────────────────────────
    _d3m_dt  = today - timedelta(days=90)
    _d1y_dt  = today - timedelta(days=365)
    _d5y_dt  = today - timedelta(days=1825)
    _d10y_dt = today - timedelta(days=3650)

    code_based_items = []

    for _ck, _s in disease_stats.items():
        _dc  = (_s.get("diag_code") or _ck).strip()
        if not _dc or _dc in ("$", "해당없음"):
            continue
        _nm  = _s.get("name") or _ck
        _hp  = " / ".join(list(_s["hospitals"])[:2]) or "정보 없음"
        # 투약일수: 처방조제(pharma)에서만 확인
        _med_pharma = _s["med_dates_pharma"]

        def _ci(q, reason, date="", is_inp=False, inp_days=0, inp_count=0,
                visit_count=0, is_surg=False, surg_name=None, med_days=0,
                weight="mid", rule_id="", evidence=None,
                _dc=_dc, _nm=_nm, _hp=_hp, _s=_s):
            return {
                "date": date or _s.get("latest_date",""),
                "code": _dc, "disease": _nm, "hospital": _hp,
                "duty_question": q, "reason": reason,
                "is_inpatient": is_inp, "inpatient_days": inp_days,
                "inpatient_count": inp_count,
                "visit_count": visit_count,
                "first_diagnosis_date": _s.get("first_date", ""),
                "is_surgery": is_surg, "surgery_name": surg_name,
                "med_days": med_days, "weight": weight, "_source": "code",
                "_rule_id": rule_id,
                "_evidence": evidence or {},
            }

        # ── 기간별 날짜 필터 ──
        inp_3m   = _dts_in_range(_s["inpatient_dates"], _d3m_dt)
        surg_3m  = _dts_in_range(_s["surgery_dates"], _d3m_dt)
        inp_10y  = _dts_in_range(_s["inpatient_dates"], _d10y_dt)
        surg_10y = _dts_in_range(_s["surgery_dates"], _d10y_dt)
        all_5y   = _dts_in_range(_s["visit_dates"] | _s["inpatient_dates"] | _s["surgery_dates"], _d5y_dt)
        inp_5y   = _dts_in_range(_s["inpatient_dates"], _d5y_dt)
        surg_5y  = _dts_in_range(_s["surgery_dates"], _d5y_dt)
        # 통원횟수: 기본진료 외래(통원)만 — visit_dates (입원 제외)
        visit_3m  = _dts_in_range(_s["visit_dates"], _d3m_dt)
        visit_10y = _dts_in_range(_s["visit_dates"], _d10y_dt)
        visit_5y  = _dts_in_range(_s["visit_dates"], _d5y_dt)

        # ── 입원일수/횟수 계산 (기본진료 기준) ──
        _inp_days_map = _s.get("_inpatient_days_map", {})
        # 입원일수 = 날짜별 내원일수 합산
        _inp3m_days  = sum(_inp_days_map.get(d, 1) for d in inp_3m)  if inp_3m  else 0
        _inp10y_days = sum(_inp_days_map.get(d, 1) for d in inp_10y) if inp_10y else 0
        _inp5y_days  = sum(_inp_days_map.get(d, 1) for d in inp_5y)  if inp_5y  else 0
        # 입원횟수 = 해당 기간 내 입원 날짜 수
        _inp3m_count  = len(inp_3m)
        _inp10y_count = len(inp_10y)
        _inp5y_count  = len(inp_5y)

        # ── 투약일수 (처방조제에서만) ──
        presc_3m  = _max_presc(_med_pharma, _d3m_dt)
        presc_10y = _max_presc(_med_pharma, _d10y_dt)
        presc_5y  = _max_presc(_med_pharma, _d5y_dt)

        _sn = next(iter(_s["surgeries"]), None)
        _wt = ("critical" if _code_in(_dc, ("C","I60","I61","I62","I63","I64","I21","I22","K74"))
               else "high" if _code_in(_dc, ("I10","I11","I12","I13","I14","I15","E10","E11","E12","E13","E14","I20"))
               else "mid")

        if inp_3m:
            code_based_items.append(_ci("Q1", f"3개월 이내 입원 ({_inp3m_days}일) — 기본진료 확정",
                date=max(inp_3m), is_inp=True, inp_days=_inp3m_days, inp_count=_inp3m_count,
                visit_count=len(visit_3m), med_days=presc_3m, weight=_wt,
                rule_id="R-Q1-INP-3M", evidence={"dates": inp_3m, "actual_days": _inp3m_days}))
        if surg_3m:
            code_based_items.append(_ci("Q1", f"3개월 이내 수술: {_sn or '수술'} — 세부진료 확정",
                date=max(surg_3m), is_surg=True, surg_name=_sn,
                visit_count=len(visit_3m), med_days=presc_3m, weight=_wt,
                rule_id="R-Q1-SURG-3M", evidence={"dates": surg_3m, "surgery": _sn}))

        if product_type == "간편심사 (유병자 3-5-5 기준)":
            if inp_10y:
                code_based_items.append(_ci("Q2", f"10년 이내 입원 ({_inp10y_days}일) — 기본진료 확정",
                    date=max(inp_10y), is_inp=True, inp_days=_inp10y_days, inp_count=_inp10y_count,
                    visit_count=len(visit_10y), med_days=presc_10y, weight=_wt,
                    rule_id="R-Q2-INP-10Y", evidence={"dates": inp_10y, "actual_days": _inp10y_days}))
            if surg_10y:
                code_based_items.append(_ci("Q2", f"10년 이내 수술: {_sn or '수술'} — 세부진료 확정",
                    date=max(surg_10y), is_inp=bool(inp_10y), inp_days=_inp10y_days, inp_count=_inp10y_count,
                    visit_count=len(visit_10y), med_days=presc_10y,
                    is_surg=True, surg_name=_sn, weight=_wt,
                    rule_id="R-Q2-SURG-10Y", evidence={"dates": surg_10y, "surgery": _sn}))
            if _code_in(_dc, SIMPLE_Q3_CODES) and all_5y:
                code_based_items.append(_ci("Q3", f"5년 이내 6대 중증질환: {_nm} (코드: {_dc})",
                    date=max(all_5y), is_inp=bool(inp_5y), inp_days=_inp5y_days, inp_count=_inp5y_count,
                    visit_count=len(visit_5y), med_days=presc_5y,
                    is_surg=bool(surg_5y), surg_name=_sn if surg_5y else None, weight="critical",
                    rule_id="R-Q3-CRITICAL-5Y", evidence={"code": _dc, "matched_prefix": "SIMPLE_Q3_CODES"}))
        else:
            if inp_10y:
                code_based_items.append(_ci("Q4", f"10년 이내 입원 ({_inp10y_days}일) — 기본진료 확정",
                    date=max(inp_10y), is_inp=True, inp_days=_inp10y_days, inp_count=_inp10y_count,
                    visit_count=len(visit_10y), med_days=presc_10y, weight=_wt,
                    rule_id="R-Q4-INP-10Y", evidence={"dates": inp_10y, "actual_days": _inp10y_days}))
            if surg_10y:
                code_based_items.append(_ci("Q4", f"10년 이내 수술: {_sn or '수술'} — 세부진료 확정",
                    date=max(surg_10y), is_inp=bool(inp_10y), inp_days=_inp10y_days, inp_count=_inp10y_count,
                    visit_count=len(visit_10y), med_days=presc_10y,
                    is_surg=True, surg_name=_sn, weight=_wt,
                    rule_id="R-Q4-SURG-10Y", evidence={"dates": surg_10y, "surgery": _sn}))
            if len(visit_10y) >= 7 and not inp_10y and not surg_10y:
                code_based_items.append(_ci("Q4", f"10년 이내 7회이상 통원 ({len(visit_10y)}회) — 기본진료 확정",
                    visit_count=len(visit_10y), med_days=presc_10y, weight=_wt,
                    rule_id="R-Q4-VISIT-7", evidence={"visit_count": len(visit_10y), "dates": visit_10y}))
            if presc_10y >= 30 and not inp_10y and not surg_10y:
                code_based_items.append(_ci("Q4", f"10년 이내 30일이상 투약 ({presc_10y}일) — 처방조제 확정",
                    visit_count=len(visit_10y), med_days=presc_10y, weight=_wt,
                    rule_id="R-Q4-MED-30D", evidence={"presc_days": presc_10y, "source": "처방조제"}))
            if _code_in(_dc, HEALTH_Q5_CODES) and all_5y:
                code_based_items.append(_ci("Q5", f"5년 이내 중증질환: {_nm} (코드: {_dc})",
                    date=max(all_5y), is_inp=bool(inp_5y), inp_days=_inp5y_days, inp_count=_inp5y_count,
                    visit_count=len(visit_5y), med_days=presc_5y,
                    is_surg=bool(surg_5y), surg_name=_sn if surg_5y else None,
                    weight="critical" if _wt == "critical" else "high",
                    rule_id="R-Q5-CRITICAL-5Y", evidence={"code": _dc, "matched_prefix": "HEALTH_Q5_CODES"}))

    # ── AI 전달용 raw_text 구축 ───────────────────────────────────
    raw_text_lines = []
    seen_code_dates = set()

    for _, row in df.iterrows():
        if row_is_junk(row): continue
        ftype    = str(row.get("_ftype", ""))
        dept     = get_val(row, ["진단과"])
        if ftype in ("basic", "unknown") and dept.replace(" ", "") == "일반의":
            continue
        date_str = get_val(row, ["진료개시일", "진료시작일", "진료일", "조제일자", "처방일"])
        # AI raw_text에도 약국 코드는 질병코드로 전달하지 않음
        code_raw = "" if ftype == "pharma" else get_val(row, ["코드", "상병코드", "진단코드"])
        code_str = normalize_code(code_raw)
        name_str = get_val(row, ["상병명", "약품명", "진료내역", "행위명"])
        hospital = get_val(row, ["병·의원", "기관명", "요양기관명"])
        in_out   = get_val(row, ["입내원구분", "입원외래구분", "입원", "외래", "구분"])
        m_days   = get_val(row, ["내원일수", "투약일수", "요양일수"])
        cost_raw = get_val(row, ["총진료비", "진료비", "총 진료비"])

        if not date_str and not name_str: continue
        if ftype == "pharma" and not m_days: continue

        if ftype == "detail":
            act_name_raw = get_val(row, ["행위명칭", "행위명", "진료내역", "처치"])
            display_name = name_str[:20]
            act_norm = re.sub(r"[\s\d]", "", (act_name_raw or ""))[:15]
            dedup_key = (code_str, date_str, ftype, act_norm)
        else:
            display_name = name_str[:20]
            name_norm_dedup = re.sub(r"[\s\d]", "", name_str)[:15]
            dedup_key = (code_str or name_norm_dedup, date_str, ftype, "")
        if dedup_key in seen_code_dates:
            continue
        seen_code_dates.add(dedup_key)

        inpatient_flag = "입원" if "입원" in in_out else ""
        line_date = parse_date(date_str) or date_str

        act_suffix = ""
        if ftype == "detail":
            _act = get_val(row, ["행위명칭", "행위명", "진료내역", "처치"])
            if _act:
                act_suffix = f" 행위:{_act[:25]}"
        raw_text_lines.append(
            f"{line_date} [{ftype}] {code_str} {display_name}{act_suffix} {hospital[:10]}"
            + (f" 투약{m_days}일" if m_days and m_days != "0" else "")
            + (f" 진료비{cost_raw}" if cost_raw else "")
            + (f" {inpatient_flag}" if inpatient_flag else "")
        )

    # DataFrame/원본 레코드 해제 — 이후 disease_stats만 사용
    del df, all_records
    gc.collect()

    today_str = today.strftime('%Y-%m-%d')
    d_3m  = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    d_1y  = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    d_5y  = (today - timedelta(days=1825)).strftime('%Y-%m-%d')
    d_10y = (today - timedelta(days=3650)).strftime('%Y-%m-%d')

    # ── 약 변경 감지 ──────────────────────────────────────────────
    drug_change_summary = []

    for group_key, s in disease_stats.items():
        drugs_in_90     = s.get("drug_names_in_90", set())
        drugs_before_90 = s.get("drug_names_before_90", set())
        if not drugs_in_90 or not drugs_before_90:
            continue

        info_in_90     = {extract_drug_info(d)[0]: extract_drug_info(d)[1] for d in drugs_in_90}
        info_before_90 = {extract_drug_info(d)[0]: extract_drug_info(d)[1] for d in drugs_before_90}
        norm_in_90     = set(info_in_90.keys())
        norm_before_90 = set(info_before_90.keys())

        stopped_drugs   = norm_before_90 - norm_in_90
        new_drugs       = norm_in_90 - norm_before_90
        continued_drugs = norm_in_90 & norm_before_90

        dose_increased = []
        dose_decreased = []
        for drug_name in continued_drugs:
            dose_before = info_before_90.get(drug_name, 0)
            dose_after  = info_in_90.get(drug_name, 0)
            if dose_before > 0 and dose_after > 0:
                if dose_after > dose_before:
                    dose_increased.append(f"{drug_name} ({dose_before}→{dose_after})")
                elif dose_after < dose_before:
                    dose_decreased.append(f"{drug_name} ({dose_before}→{dose_after})")

        has_change = bool(new_drugs or dose_increased)
        if has_change or stopped_drugs:
            if new_drugs and stopped_drugs:
                change_type = "약 종류 변경"
            elif new_drugs:
                change_type = "새 약 추가"
            elif dose_increased:
                change_type = "용량 증가"
            else:
                change_type = "약 중단"

            if new_drugs or dose_increased:
                drug_change_summary.append({
                    "group":          group_key,
                    "name":           s.get("name", group_key),
                    "continued":      list(continued_drugs)[:3],
                    "stopped":        list(stopped_drugs)[:3],
                    "new":            list(new_drugs)[:3],
                    "dose_increased": dose_increased[:3],
                    "dose_decreased": dose_decreased[:3],
                    "change_type":    change_type,
                })

    if product_type == "간편심사 (유병자 3-5-5 기준)":
        for dc in drug_change_summary:
            change_type = dc["change_type"]
            new_d  = dc.get("new", [])
            inc_d  = dc.get("dose_increased", [])
            reason_parts = []
            if change_type == "약 종류 변경":
                reason_parts.append(f"3개월 이전 약에서 신규 약으로 변경: {', '.join(new_d[:2])}")
            elif change_type == "새 약 추가":
                reason_parts.append(f"3개월 이전부터 복용 중 새 약 추가: {', '.join(new_d[:2])}")
            elif change_type == "용량 증가":
                reason_parts.append(f"복용 중 약 용량 증가: {', '.join(inc_d[:2])}")
            else:
                if new_d: reason_parts.append(f"새 약 추가: {', '.join(new_d[:2])}")
                if inc_d: reason_parts.append(f"용량 증가: {', '.join(inc_d[:2])}")

            _grp_s = disease_stats.get(dc["group"], {})
            _pm = _grp_s.get("med_dates_pharma", {}) if _grp_s else {}
            _in_3m_dates = [d for d in _pm if _dts_in_range([d], _d3m_dt)]
            _date = max(_in_3m_dates) if _in_3m_dates else ""

            code_based_items.append({
                "date":           _date or "",
                "code":           dc["group"] if dc["group"] else "-",
                "disease":        dc["name"],
                "hospital":       "처방조제내역",
                "duty_question":  "Q1",
                "reason":         f"3개월 이내 처방 변경 ({change_type}) — 처방조제 확정 | " + " / ".join(reason_parts),
                "is_inpatient":   False,
                "inpatient_days": 0,
                "is_surgery":     False,
                "surgery_name":   None,
                "med_days":       0,
                "weight":         "high",
                "_source":        "code",
            })

    drug_change_text = ""
    if drug_change_summary:
        drug_change_text = "\n[처방약 변경 감지 결과 — 간편심사 Q1 판단 필수 참고]\n"
        for dc in drug_change_summary:
            drug_change_text += (
                f"- 질환: {dc['name']} / 변경유형: {dc['change_type']}\n"
                f"  · 3개월 이전 약(중단): {', '.join(dc['stopped']) if dc['stopped'] else '없음'}\n"
                f"  · 3개월 이내 신규약(추가/변경): {', '.join(dc['new']) if dc['new'] else '없음'}\n"
                f"  · 용량 증가 약(가입불가): {', '.join(dc['dose_increased']) if dc['dose_increased'] else '없음'}\n"
                f"  · 용량 감소 약(가입가능): {', '.join(dc['dose_decreased']) if dc['dose_decreased'] else '없음'}\n"
                f"  · 계속 유지 중인 약: {', '.join(dc['continued']) if dc['continued'] else '없음'}\n"
            )
        drug_change_text += (
            "※ 가입 불가: 약 종류 변경 / 새 약 추가 / 용량 증가\n"
            "※ 가입 가능: 동일 약 지속 복용(변경 없음) / 용량 감소 / 약 중단\n"
        )

    # ── 처방 종료일 계산 ─────────────────────────────────────────
    earliest_available_date = None
    prescription_end_details = []

    for group_key, s in disease_stats.items():
        med_dict = s["med_dates_pharma"] if s["has_pharma"] and s["med_dates_pharma"] else s["med_dates_basic"]
        if not med_dict:
            continue
        for presc_date_str, m_days_val in med_dict.items():
            if not presc_date_str or m_days_val <= 0:
                continue
            try:
                presc_dt = datetime.strptime(presc_date_str, "%Y-%m-%d")
            except ValueError:
                continue
            days_ago = (today - presc_dt).days
            if days_ago > 90:
                continue
            end_dt       = presc_dt + timedelta(days=m_days_val - 1)
            available_dt = end_dt + timedelta(days=1)
            prescription_end_details.append({
                "name":       s.get("name", group_key),
                "presc_date": presc_date_str,
                "m_days":     m_days_val,
                "end_date":   end_dt.strftime("%Y-%m-%d"),
                "available":  available_dt.strftime("%Y-%m-%d"),
                "already_ok": available_dt <= today,
            })
            if earliest_available_date is None or available_dt > earliest_available_date:
                earliest_available_date = available_dt

    presc_end_text = ""
    if prescription_end_details:
        presc_end_text = "\n[3개월 이내 처방 종료일 분석 — 가입 가능 날짜 계산]\n"
        for p in prescription_end_details:
            status = "✅ 이미 복약 완료 (가입 가능)" if p["already_ok"] else f"❌ 복약 중 (가입불가 ~ {p['end_date']})"
            presc_end_text += (
                f"- 질환: {p['name']}\n"
                f"  처방일: {p['presc_date']} / 투약일수: {p['m_days']}일 / 종료일: {p['end_date']}\n"
                f"  → 가입 가능 날짜: {p['available']} / 상태: {status}\n"
            )
        if earliest_available_date and earliest_available_date > today:
            presc_end_text += (
                f"\n★ 전체 처방 기준 최소 가입 가능 날짜: {earliest_available_date.strftime('%Y-%m-%d')}\n"
                f"  (이 날짜 이전에 청약하면 3개월 이내 투약으로 Q1 해당)\n"
            )
        elif earliest_available_date and earliest_available_date <= today:
            presc_end_text += "\n★ 3개월 이내 처방이 있으나 모두 복약 완료 상태 — 투약 관련 Q1은 면제 가능\n"

    # ── 날짜 태그 필터링 ─────────────────────────────────────────
    filtered_lines = []
    for line in raw_text_lines:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
        if not date_match:
            filtered_lines.append(line)
            continue
        line_date = date_match.group(1)
        try:
            dt = datetime.strptime(line_date, "%Y-%m-%d")
        except ValueError:
            filtered_lines.append(line)
            continue
        days_ago = (today - dt).days
        if days_ago < 0 or days_ago > 3650:
            continue
        tags = []
        if days_ago <= 90:   tags.append("IN_3M")
        if days_ago <= 365:  tags.append("IN_1Y")
        if days_ago <= 1825: tags.append("IN_5Y")
        if days_ago <= 3650: tags.append("IN_10Y")
        filtered_lines.append(line + " [" + ",".join(tags) + "]")

    raw_text = "\n".join(filtered_lines[:800])

    # ── 통원횟수·처방일수 집계 ───────────────────────────────────
    d_10y_dt = today - timedelta(days=3650)
    visit_count_lines = []
    for _code, _s in disease_stats.items():
        _visits_in_10y = []
        for _d in _s["visit_dates"]:
            try:
                if datetime.strptime(_d, "%Y-%m-%d") >= d_10y_dt:
                    _visits_in_10y.append(_d)
            except ValueError:
                pass
        _med_dict = _s["med_dates_pharma"] if _s.get("has_pharma") and _s["med_dates_pharma"] else _s["med_dates_basic"]
        _max_presc_days = 0
        for _pd, _pv in _med_dict.items():
            try:
                if datetime.strptime(_pd, "%Y-%m-%d") >= d_10y_dt:
                    if _pv > _max_presc_days:
                        _max_presc_days = _pv
            except ValueError:
                pass
        _name = _s.get("name", "")[:15]
        if _visits_in_10y:
            _cnt   = len(_visits_in_10y)
            _first = min(_visits_in_10y) if _visits_in_10y else "-"
            _last  = max(_visits_in_10y) if _visits_in_10y else "-"
            _presc_note = f" 최대처방{_max_presc_days}일" if _max_presc_days > 0 else ""
            _7day_flag = " ★7회이상" if _cnt >= 7 else ""
            visit_count_lines.append(
                f"[통원집계] {_code} {_name} 10년내통원{_cnt}회 ({_first}~{_last}){_presc_note}{_7day_flag}"
            )
    if visit_count_lines:
        raw_text = "[10년내 질병코드별 통원횟수 집계 — Q4 7회이상통원 판단 기준]\n" \
                   + "\n".join(visit_count_lines) + "\n\n" + raw_text
    if cross_surgery_hints:
        raw_text = "[기본/세부 동일일자 교차검증 — 수술 추정 근거]\n" \
                   + "\n".join(f"- {h}" for h in cross_surgery_hints[:80]) + "\n\n" + raw_text

    # ── 최초 진단일 정보 (동일코드 기준) ────────────────────────────
    first_diag_lines = []
    for _ck, _s in disease_stats.items():
        _fd = _s.get("first_date", "2099-12-31")
        if _fd and _fd != "2099-12-31":
            _dc = _s.get("diag_code") or _ck
            _nm = _s.get("name", "")[:20]
            first_diag_lines.append(f"  {_dc} {_nm} 최초={_fd} 최종={_s.get('latest_date','')}")
    if first_diag_lines:
        raw_text = "[질병별 최초·최종 진단일 — 고지사항 최초진단일 확인]\n" \
                   + "\n".join(first_diag_lines[:100]) + "\n\n" + raw_text

    if drug_change_text:
        raw_text = drug_change_text + "\n" + raw_text
    if presc_end_text:
        raw_text = presc_end_text + "\n" + raw_text

    # ── raw_text 길이 제한 (Render 512MB 메모리 제약) ─────────────
    MAX_RAW_TEXT_LEN = 30_000
    if len(raw_text) > MAX_RAW_TEXT_LEN:
        raw_text = raw_text[:MAX_RAW_TEXT_LEN] + "\n... (truncated)"

    # ── 프롬프트 구성 ─────────────────────────────────────────────
    if product_type == "건강체/표준체 (일반심사)":
        criteria_text = f"""
[건강체/표준체 알릴의무 4문항] (기준일: {today_str})
Q1. 최근 3개월({d_3m} 이후) — 태그 [IN_3M] 항목만: 질병확정진단 / 의심소견 / 입원·수술·추가검사 필요소견 / 치료 / 투약
Q2. 최근 3개월({d_3m} 이후) — 태그 [IN_3M] 항목만: 혈압강하제·신경안정제·수면제·각성제·진통제·마약류 상시 복용
Q3. 최근 1년({d_1y} 이후) — 태그 [IN_1Y] 항목만: 진찰 후 이상소견으로 추가검사(재검사) 받은 사실
    ★ Q3 추가검사(재검사) 정확한 정의:
       [해당 O] 진찰 결과 이상소견이 확인되어 더 정확한 진단을 위해 시행한 추가 검사
               예) X-RAY 촬영 후 이상소견 → MRI·CT·혈액검사 등 추가 시행 (당일이 아니어도 동일 질병으로 연결되면 해당)
       [해당 X — 반드시 Q3 면제] 아래 경우는 절대 Q3 배정 불가:
               - 단순 1회 검사만 시행하고 종결 (X-RAY 1회, 혈액검사 1회 등 단독 검사)
               - 이상소견 없이 단순 확인·스크리닝 목적의 검사
               - 정기검사 또는 추적관찰 (치료 없이 유지 상태에서 주기적으로 시행하는 검사)
               - 검사 후 추가 검사 없이 단순 치료로만 이어진 경우 → Q3 아닌 Q1/Q4로 판단
Q4. 최근 10년({d_10y} 이후) — 태그 [IN_10Y] 항목만:
    - 입원
    - 수술 (제왕절개 포함)
    - 계속하여 7일 이상 치료 ★ = 동일 질병코드(KCD) 기준 통원횟수 7회 이상 ([통원집계]에서 10년내통원7회 이상인 코드)
    - 계속하여 30일 이상 투약 (단일 처방 30일 이상 OR 만성질환 매월 지속 처방)
Q5. 최근 5년({d_5y} 이후) — 태그 [IN_5Y] 항목만: 아래 중증질환 확정진단만 해당
    ① 암 (악성신생물): C00~C97
    ② 백혈병: C91~C95 (암 포함)
    ③ 고혈압: I10~I15
    ④ 협심증: I20
    ⑤ 심근경색: I21~I22
    ⑥ 심장판막증: I05~I09, I34~I39
    ⑦ 간경화증: K74
    ⑧ 뇌출혈: I60~I62
    ⑨ 뇌경색: I63~I64
    ⑩ 당뇨병: E10~E14
    ⑪ 에이즈: B20~B24, Z21
    ★ Q5 면제: 위 코드 범위에 해당하지 않는 모든 질환 → Q5 배정 불가"""
    else:
        criteria_text = f"""
[간편심사(유병자 3-5-5) 알릴의무 3문항] (기준일: {today_str})
Q1. 최근 3개월({d_3m} 이후) — 태그 [IN_3M] 항목만:
    ① 질병확정진단 / 의심소견 / 추가검사필요소견 / 입원 / 수술
    ② 3개월 이전부터 복용하던 약의 변화 → 아래 기준으로 Q1 판단:
       [가입 불가 → Q1 해당]
       - 약 종류 자체가 바뀐 경우 (성분명 변경)
       - 3개월 이내 완전히 새로운 약이 추가된 경우
       - 동일 약의 용량이 증가한 경우 (예: 메트포르민 500mg → 1000mg)
       [가입 가능 → Q1 해당 아님]
       - 동일 약을 변경 없이 계속 복용 중인 경우
       - 동일 약의 용량만 감소한 경우 (예: 메트포르민 1000mg → 500mg)
       - 복용하던 약을 중단한 경우
Q2. 최근 10년({d_10y} 이후) — 태그 [IN_10Y] 항목만: 입원 또는 수술(제왕절개 포함)
Q3. 최근 5년({d_5y} 이후) — 태그 [IN_5Y] 항목만: 아래 6대 중증질환 확정진단만 해당
    ① 암: C00~C97 (악성신생물 전체)
    ② 뇌출혈: I60~I62
    ③ 뇌경색: I63~I64
    ④ 협심증: I20
    ⑤ 심근경색: I21~I22
    ⑥ 심장판막증: I05~I09, I34~I39
    ⑦ 간경화: K74

    ★ Q3 절대 면제 (아무리 심해도 Q3 배정 불가):
    - 당뇨병 (E10~E14 계열) → Q3 해당 아님, Q4만 가능
    - 고혈압 (I10~I15) → Q3 해당 아님
    - 무릎관절증·척추협착 등 근골격계 → Q3 해당 아님
    - 만성신부전·갑상선·고지혈증 등 → Q3 해당 아님
    - 위/대장 용종 → Q3 해당 아님
    - 6대 중증질환 KCD 코드가 아닌 모든 질환 → Q3 배정 절대 불가

[면제] 통원횟수 7회 미만인 경우 / 30일 미만 단순 투약 / 6대 중증질환 KCD 코드가 아닌 모든 질환
[약 변경 면제] 3개월 이전부터 동일 약 지속 복용(변경 없음) → 면제 / 동일 약 용량만 감소 → 면제"""

    is_health = product_type == "건강체/표준체 (일반심사)"
    step2_tag_rules = (
        "건강체/표준체 기준:\n"
        "- [IN_3M] 있어야만 → Q1, Q2 배정 가능\n"
        "- [IN_1Y] 있어야만 → Q3 배정 가능\n"
        "- [IN_5Y] 있어야만 → Q5 배정 가능\n"
        "- [IN_10Y] 있어야만 → Q4 배정 가능\n"
        "- [IN_3M] 없으면 → Q1/Q2 배정 절대 불가\n"
        "- [IN_10Y]만 있고 [IN_3M] 없으면 → Q4만 배정 (Q1 절대 불가)\n"
        "★ 사용 가능한 질문번호: Q1, Q2, Q3, Q4, Q5 (Q4=10년 이내 입원/수술/7일이상/30일이상, Q5=5년 이내 중증)"
    ) if is_health else (
        "간편심사 기준:\n"
        "- [IN_3M] 있어야만 → Q1 배정 가능\n"
        "- [IN_5Y] 있어야만 → Q3 배정 가능\n"
        "- [IN_10Y] 있어야만 → Q2 배정 가능\n"
        "- [IN_3M] 없으면 → Q1 배정 절대 불가\n"
        "- [IN_10Y]만 있고 [IN_3M] 없으면 → Q2만 배정 (Q1 절대 불가)\n"
        "★ 사용 가능한 질문번호: Q1, Q2, Q3 뿐. Q4/Q5는 절대 사용 금지."
    )

    if is_health:
        step4_surgery_text = """
━━━━━━━━━━━━━━━━━━━━━━━━━━
[4단계: Q4 수술 인정 목록 — 반드시 is_surgery=true]
━━━━━━━━━━━━━━━━━━━━━━━━━━

[소화기 내시경 수술]
- K63.5/AK635 결장용종 → 대장내시경 용종절제술 ★반드시 수술
- K31/AK31 위용종 → 위내시경 용종절제술
- K92.1 혈변+내시경 지혈술 → 수술
- 위/대장 폴립, 용종 관련 진료비 30만원 이상 외래 → 수술 가능성

[치과 수술]
- K08.1/AK081 발치 → 발치술 ★반드시 수술
- K04.7/AK047 근단주위농양 절개 → 수술
- 임플란트 시술 → 수술

[안과 수술]
- H25/AH25 백내장 → 백내장 수술 (진료비 50만원 이상)
- H33/AH33 망막박리 → 망막수술
- H40/AH40 녹내장 수술

[정형/신경외과 수술]
- 척추/관절 진료비 50만원 이상 + 입원 → 수술 가능
- 골절(S계열) + 수술 키워드 → 골절 수술

[산부인과 수술]
- O84/AO84 제왕절개 → ★반드시 수술
- D25/AD25 자궁근종 절제 → 수술
- N83/AN83 난소낭종 제거 → 수술

[피부/성형외과 수술]
- L02/AL02 농양 절개배농 → 수술
- M72.66/AM7266 괴사성근막염 → 광범위절제술 ★반드시 수술 (critical)
- L84/AL84 티눈·굳은살 → 행위명에 제거술·소작·레이저·냉동 포함 시 ★반드시 수술
- 행위명에 "제거술","소작술","냉동치료","레이저절제","배농술","절개배농" 포함 → 수술
- 피부과 진료비 10만원 이상 + 절개·제거·소작 키워드 → 수술

[공통 수술 판단 규칙]
- 입원 동반 + 외과/흉부외과/성형외과/산부인과 → 수술 가능성 높음
- 진료비 총액 100만원 이상 외래 1회 → 수술 강력 의심
- 병명/진료내역에 절제·절개·봉합·이식·성형·제거·적출 포함 → 수술"""

        step5_q4_exempt_text = """
▶ Q4 반드시 면제 처리 항목:
  ① 동일 질병코드 통원횟수 6회 이하 (7회 미만), 투약 30일 미만, 입원 없음, 수술 없음
     ★ "계속하여 7일 이상 치료"는 처방일수가 아닌 통원횟수 기준 — [통원집계]에서 해당 코드 통원횟수가 7회 미만이면 반드시 면제
     ★★ 처방일수 7일 이상이라도 통원횟수 7회 미만이면 "7일 이상 치료" 해당 아님
     ★★★ 이 규칙은 정신건강의학과(F계열)·신경과 포함 모든 진료과에 동일하게 적용
        정신건강의학과 1회 방문 + 투약 30일 미만 → Q4 절대 면제 (weight=high여도 면제)
  ② 단순 감기·비염·인후염·결막염·두드러기·타박상·염좌 (통원횟수 무관하게 Q4 면제)
  ③ 치과 스케일링·단순 충치 보존치료 (발치·임플란트 제외)
  ④ 한방 단순 침구치료 (수술/입원 미동반)
  ⑤ 단순 통원 검사만 받고 종결 (수술/입원/통원7회이상 치료 없음)
  ⑥ 방광염·요로감염 단순 항생제 투약 (1회성)
  ⑦ 알레르기성 피부염 단순 외래 1~2회
  ⑧ 정신건강의학과·신경과·심리검사 단순 1회 방문 (통원 7회 미만, 입원 없음, 투약 30일 미만) → Q4 면제

★★ 질병코드 원칙: 질병코드(KCD)는 반드시 기본진료에서 확인된 코드만 사용.
   처방조제(약품명)로부터 질병코드를 추정/예측하지 마세요.
   처방조제 데이터는 투약일수·약 변경 판단에만 사용합니다.

▶ 만성질환 30일이상 투약 판단:
  - 당뇨(E11계열): 매월 지속 처방 확인 시 → med_days=365, Q4 해당 (Q3 아님)
  - 고혈압(I10계열): 매월 지속 처방 → med_days=365, Q4 해당 (Q3 아님)
  - 고지혈증(E78계열): 매월 지속 처방 → med_days=365, Q4 해당
  - 갑상선(E03/E05): 매월 지속 처방 → med_days=365, Q4 해당
  - 단, 3개월 이내에만 처방 기록이 있고 이전 기록 없음 → Q1 해당 가능"""

        json_duty_q_values = "Q1 또는 Q2 또는 Q3 또는 Q4 또는 Q5"
        json_hit_fields = """\
  "q1_hit": true또는false, "q1_reason": "사유",
  "q2_hit": true또는false, "q2_reason": "해당 약물명 또는 없음",
  "q3_hit": true또는false, "q3_reason": "사유",
  "q4_hit": true또는false, "q4_reason": "입원/수술/7일이상/30일이상 중 해당 사유",
  "q5_hit": true또는false, "q5_reason": "중증질환명 또는 없음","""

        step5_q3_health_text = (
            "\n▶ 건강체 Q3 추가검사(재검사) 판단 기준 (★핵심 규칙):\n"
            "  Q3는 '진찰 후 이상소견 → 추가 검사' 두 단계가 반드시 존재해야 함.\n\n"
            "  [Q3 해당 O — 반드시 포함]:\n"
            "  - 진찰 결과 이상소견 발견 → 더 정확한 진단을 위해 추가 검사 시행\n"
            "  - 예: 진찰 후 X-RAY → 이상소견 → MRI/CT/혈액검사/초음파 등 추가 시행\n"
            "  - 추가 검사는 당일이 아니어도 됨 (동일 질병코드로 연결된 경우)\n"
            "  - 검사 결과 이후 치료로 이어졌어도, 이상소견으로 추가 검사를 받은 사실 자체가 Q3\n\n"
            "  [Q3 해당 X — 반드시 면제]:\n"
            "  - 단순 1회 검사만 시행하고 종결 (X-RAY 1회, 혈액검사 1회, 초음파 1회 등 단독)\n"
            "  - 이상소견 없이 단순 확인·스크리닝 목적의 1회 검사\n"
            "  - 정기검사·추적관찰 (치료 없이 병증이 유지되는 상태에서 시행하는 주기적 검사)\n"
            "  - 검사 1종만 찍고 추가 검사 없이 바로 치료로 이어진 경우 → Q1 또는 Q4로만 처리\n"
            "  - 건강검진 항목으로 시행된 검사"
        )
        q3_diabetes_note = "(Q4만)"
    else:
        step4_surgery_text = (
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "[4단계: Q2 수술 인정 목록 — 반드시 is_surgery=true]\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "간편심사 Q2는 입원 또는 수술만 해당. 아래 수술 판단 기준을 적용하세요.\n\n"
            "- O84/AO84 제왕절개 → ★반드시 수술\n"
            "- K63.5/AK635 결장용종 → 대장내시경 용종절제술 = 수술\n"
            "- K08.1/AK081 발치 → 발치술 = 수술\n"
            "- H25/AH25 백내장 수술 (진료비 50만원 이상)\n"
            "- D25/AD25 자궁근종 절제, N83/AN83 난소낭종 제거 → 수술\n"
            "- M72.66/AM7266 괴사성근막염 → 광범위절제술 = 수술 (critical)\n"
            "- 병명/진료내역에 절제·절개·봉합·이식·성형·제거·적출 포함 → 수술\n"
            "- 입원 동반 + 외과/흉부외과/성형외과/산부인과 → 수술 가능성 높음\n"
            "★ 7일 이상 치료, 30일 이상 투약은 간편심사 Q2 해당 없음 (건강체 Q4 기준). Q2에 배정 금지."
        )
        step5_q4_exempt_text = (
            "\n▶ 간편심사 Q2 면제 기준:\n"
            "  - 입원 없음 AND 수술 없음 → Q2 배정 절대 불가 (단순 통원은 Q2 해당 없음)\n"
            "  - 7일 이상 치료·30일 이상 투약 만으로는 Q2 해당 없음 (건강체 Q4 기준임)"
        )
        json_duty_q_values = "Q1 또는 Q2 또는 Q3 (Q4/Q5는 절대 사용 금지)"
        json_hit_fields = (
            '  "simple_q1_hit": true또는false, "simple_q1_reason": "사유",\n'
            '  "simple_q2_hit": true또는false, "simple_q2_reason": "입원 또는 수술 상세",\n'
            '  "simple_q3_hit": true또는false, "simple_q3_disease": "6대질병명 또는 null",'
        )
        step5_q3_health_text = ""
        q3_diabetes_note = "(간편심사 해당 없음)"

    system_prompt = f"""당신은 보험 언더라이팅 전문 AI입니다.
건강보험심사평가원(건강e음) 진료 데이터를 분석하여 보험 청약 시 알릴의무(고지의무) 해당 항목을 정확히 판단합니다.
판단의 정확도가 최우선입니다. 과잉 고지도, 누락도 모두 금물입니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━
[0단계: 데이터 파일 구조 및 교차검증 원칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━
진료 데이터는 3개 파일에서 추출됩니다:
1) 기본진료정보: 입원/외래 구분, 주상병코드, 진료시작일, 총진료비
2) 세부진료정보(진료내역): 처치및수술 분류, 행위명, 급여비용
3) 처방진료정보: 약품명, 투약일수, 처방일

★★★ 질병코드(KCD) 원칙:
- 질병코드는 반드시 기본진료에 기록된 코드만 사용하세요.
- 처방조제(약품명)로부터 질병코드를 추정·예측하지 마세요.
- 처방조제 데이터는 투약일수·약 변경 판단에만 사용합니다.
- 최초 진단일~마지막 치료일은 병원에 관계없이 동일 질병코드 기준으로 판단하세요.

★ 교차검증 규칙 (동일 날짜 기록은 반드시 함께 확인):
- 세부진료 "처치및수술" 항목 + 기본진료 고비용(30만↑) → 수술 확정
- "[기본/세부 동일일자 교차검증]"에 "교차확정" 표기된 항목은 is_surgery=true 필수
- "교차후보 ★AI판단필요" 표기된 항목은 행위명/비용/입원여부를 종합 판단하세요

★ 최초 진단일 활용:
- "[질병별 최초·최종 진단일]"에서 동일 코드의 최초 진단일을 확인하세요
- 고지사항 date 필드에는 해당 질병의 최초 진단일을 기입하세요

━━━━━━━━━━━━━━━━━━━━━━━━━━
[1단계: 코드 전처리]
━━━━━━━━━━━━━━━━━━━━━━━━━━
- 코드 앞 A(양방)/B(한방) 접두사 제거 (예: AK635→K63.5, AE1150→E11.50, BM179→M17.9)
- 숫자 1로 시작하는 코드 → I로 교정 (OCR 오류, 예: 1670→I67.0)
- $ 또는 해당없음 행 → 완전 제외
- COVID 검사(AZ115/AU071/AU072) · 예방접종(AZ코드) → 완전 제외

━━━━━━━━━━━━━━━━━━━━━━━━━━
[2단계: 날짜 태그 기반 질문 배정 — 절대 규칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━
각 진료 데이터 끝에 붙은 태그만으로 해당 질문을 결정합니다.
태그에 없는 기간의 질문에는 절대 배정하지 마세요.
{step2_tag_rules}

{criteria_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[3단계: 간편심사 약 변경 판단 — 핵심 규칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━
상단에 [처방약 변경 감지 결과]가 있으면 반드시 아래 기준으로 판단하세요.

▶ 간편심사 Q1 해당 (가입 불가):
  - 3개월 이전부터 복용하던 약의 종류가 변경된 경우
  - 3개월 이전에 없던 새로운 약이 3개월 이내 추가된 경우
  - 동일 약의 용량이 증가한 경우 (예: 500mg → 1000mg) ← 악화 신호
  → duty_question="Q1", reason에 구체적 변경 내용 명시

▶ 간편심사 Q1 해당 아님 (가입 가능):
  - 3개월 이전부터 동일 약을 변경 없이 계속 복용 중인 경우
  - 동일 약의 용량만 감소한 경우 (예: 1000mg → 500mg) ← 호전 신호
  - 복용하던 약이 중단된 경우 ← 호전 신호

━━━━━━━━━━━━━━━━━━━━━━━━━━
[3-1단계: 처방 종료일 기준 가입 가능 날짜 판단]
━━━━━━━━━━━━━━━━━━━━━━━━━━
상단에 [3개월 이내 처방 종료일 분석]이 있으면 반드시 아래 기준으로 판단하세요.

▶ 처방 종료일 계산 원칙:
  - 처방일 + 투약일수 = 처방 종료일 (마지막 복약일)
  - 처방 종료일 다음날 = 가입 가능 최소 날짜
  - 예: 3월 1일 처방 + 7일치 → 종료일 3월 7일 → 가입가능 3월 8일부터

▶ 3개월 이내 처방이 있는 경우 Q1 판단:
  - 복약 중(오늘 < 가입가능날짜): Q1 해당 → 가입불가, reason에 "복약 중 (가입가능날짜: YYYY-MM-DD)" 명시
  - 복약 완료(오늘 >= 가입가능날짜): Q1 해당 아님 → 투약 자체는 면제 가능
    단, 진단/소견 자체가 3개월 이내이면 Q1 해당 여부 별도 판단 필요

▶ 분석 데이터에서 "✅ 이미 복약 완료" 표시된 항목:
  - 해당 처방으로 인한 투약 Q1은 면제. 단 진단 자체가 3개월 이내면 Q1 해당 가능

▶ 분석 데이터에서 "❌ 복약 중" 표시된 항목:
  - 반드시 Q1 포함, reason에 "복약 중 — 가입 가능 날짜: [날짜]" 명시

{step4_surgery_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[5단계: Q3 추가검사 판단 + 면제 — 과잉 고지 방지]
━━━━━━━━━━━━━━━━━━━━━━━━━━
{step5_q3_health_text}

▶ 간편심사 Q3 절대 면제 규칙 (★최우선 적용):
  간편심사 Q3는 아래 7가지 KCD 코드 계열만 해당. 나머지는 모두 Q3 배정 절대 불가.
  허용: C00~C97(암) / I60~I62(뇌출혈) / I63~I64(뇌경색) / I20(협심증) / I21~I22(심근경색) / I05~I09·I34~I39(심장판막증) / K74(간경화)

  Q3에 절대 배정하면 안 되는 대표 질환:
  - 당뇨병 E10~E14 계열 → Q3 불가{q3_diabetes_note}
  - 고혈압 I10~I15 → Q3 불가
  - 무릎관절증 M17 / 척추협착 M48 → Q3 불가
  - 망막장애 H35 → Q3 불가
  - 위·대장 용종 K63.5 / K31 → Q3 불가
  - 메니에르 H81 / 위장출혈 K92 → Q3 불가
  - 발치 K08 / 피부질환 L98 → Q3 불가
  위 질환들이 Q3에 들어와 있으면 반드시 제거하고 올바른 질문으로 재배정하세요.

{step5_q4_exempt_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[6단계: weight(중요도) 배정]
━━━━━━━━━━━━━━━━━━━━━━━━━━
- critical: 암(C계열)/뇌졸중(I60-64)/심근경색(I21-22)/협심증(I20)/간경화(K74)/심장판막(I05-09,I34-39)/괴사성근막염
- high: 당뇨합병증/고혈압/신부전/간질환/정신질환/척추수술/관절치환
- mid: 용종절제/발치/단순 만성질환/30일이상 투약
- low: 단순 외래 통원/감기/염좌/치과 단순치료

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON:
{{
  "flagged_items": [
    {{
      "date": "YYYY-MM-DD",
      "code": "정규화된 KCD코드 (예: E11.50)",
      "disease": "질병/수술명 (한글로 명확하게)",
      "hospital": "병원명",
      "duty_question": "{json_duty_q_values}",
      "reason": "고지 판단 사유 (구체적으로, 예: 대장내시경 용종절제술=수술 해당)",
      "is_inpatient": true또는false,
      "inpatient_days": 숫자또는0,
      "is_surgery": true또는false,
      "surgery_name": "수술명 또는 null",
      "med_days": 투약일수숫자또는0,
      "weight": "critical 또는 high 또는 mid 또는 low"
    }}
  ],
  "exempt_items": [],
  {json_hit_fields}
  "drug_change_hit": true또는false, "drug_change_reason": "변경된 약 정보 또는 없음",
  "total_flagged": 숫자,
  "health_verdict": "가능 또는 조건부 또는 불가",
  "health_reason": "판단 이유 한 줄",
  "simple_verdict": "가능 또는 조건부 또는 불가",
  "simple_reason": "판단 이유 한 줄",
  "recommend": "건강체 진행 또는 간편심사 전환 권장 또는 인수 불가 가능성",
  "summary": "설계사를 위한 핵심 요약 2줄"
}}

절대 규칙: 응답은 반드시 {{ 로 시작하고 }} 로 끝나는 순수 JSON만 출력하세요.
설명, 주석, 마크다운 백틱, 전후 텍스트 일체 금지."""

    # ── Gemini API 호출 ───────────────────────────────────────────
    GEMINI_TIMEOUT_SECONDS = 240
    try:
        api_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
        )
    except TypeError:
        # Backward compatibility for older google-genai versions without HttpOptions timeout support.
        api_client = genai.Client(api_key=api_key)
    ai_result = None
    last_error = None
    raw_response = ""
    MAX_RETRIES = 5
    RETRY_DELAYS = [5, 10, 20, 40, 60]

    for attempt in range(MAX_RETRIES):
        try:
            message = api_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"고객 기준일: {today_str}\n심사 유형: {product_type}\n\n진료 데이터:\n{raw_text}",
                config=types.GenerateContentConfig(system_instruction=system_prompt),
            )
            raw_response = message.text if message.text else ""
            if not raw_response.strip():
                raise ValueError("AI 응답이 비어있습니다.")
            ai_result = extract_json(raw_response)
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                continue
            raise AnalysisError(f"AI 응답 파싱 오류: {e}", raw_response=raw_response[:800])
        except Exception as e:
            err_str = str(e)
            if ("503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str) \
                    and attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAYS[attempt]
                retry_warnings.append(f"Gemini 서버 과부하로 {wait}초 후 재시도합니다... ({attempt + 1}/{MAX_RETRIES - 1})")
                time.sleep(wait)
                continue
            raise AnalysisError(f"Gemini API 호출 오류: {e}")

    if ai_result is None:
        raise AnalysisError(f"AI 분석 실패: {last_error}")

    # 프롬프트/API 관련 대형 문자열 해제
    del raw_text, raw_response, system_prompt, raw_text_lines
    del cross_day_index, seen_code_dates
    gc.collect()

    # ── 결과 병합 ─────────────────────────────────────────────────
    summary_reports = defaultdict(list)
    flagged_codes   = set()
    merged_items    = {}
    code_claimed    = set()

    for item in (code_based_items + ai_result.get("flagged_items", [])):
        q_raw    = item.get("duty_question", "Q1")
        raw_code_key = item.get("code", item.get("disease", "unknown"))
        code_key = normalize_code(raw_code_key) or raw_code_key
        q_list   = [q.strip() for q in re.split(r"[,/\s]+", q_raw) if re.match(r"Q\d+", q.strip())]
        if not q_list:
            q_list = [q_raw.strip()]
        source = item.get("_source", "ai")

        for q in q_list:
            if product_type == "간편심사 (유병자 3-5-5 기준)":
                if q not in ("Q1", "Q2", "Q3"):
                    continue
            else:
                if q not in ("Q1", "Q2", "Q3", "Q4", "Q5"):
                    continue

            if product_type == "간편심사 (유병자 3-5-5 기준)" and q == "Q2":
                if not item.get("is_inpatient", False) and not item.get("is_surgery", False):
                    continue

            if product_type == "간편심사 (유병자 3-5-5 기준)" and q == "Q3":
                if not is_simple_q3_allowed(code_key):
                    continue

            # 전 상품 공통: 문항별 기간 강제(날짜 없음/범위 밖 제외)
            item_dt = _parse_ymd(item.get("date", ""))
            if product_type == "간편심사 (유병자 3-5-5 기준)":
                q_since_map = {"Q1": _d3m_dt, "Q2": _d10y_dt, "Q3": _d5y_dt}
            else:
                q_since_map = {"Q1": _d3m_dt, "Q2": _d3m_dt, "Q3": _d1y_dt, "Q4": _d10y_dt, "Q5": _d5y_dt}
            since_dt = q_since_map.get(q)
            if since_dt and (not item_dt or item_dt < since_dt):
                continue

            merge_key = (code_key, q)

            if source == "code":
                code_claimed.add(merge_key)
                if merge_key not in merged_items:
                    merged_items[merge_key] = _make_merged_item(item, q, code_key)
                continue

            if merge_key in code_claimed:
                continue

            if merge_key not in merged_items:
                merged_items[merge_key] = _make_merged_item(item, q, code_key)
            else:
                m = merged_items[merge_key]
                if item.get("date"):
                    m["dates"].append(item.get("date", ""))
                if item.get("is_surgery"):
                    m["is_surgery"] = True
                    if item.get("date"):
                        m["surgery_dates"].append(item.get("date", ""))
                m["inpatient_days"] = max(m["inpatient_days"], item.get("inpatient_days", 0))
                m["inpatient_count"] = max(m["inpatient_count"], item.get("inpatient_count", 0))
                m["visit_count"] = max(m["visit_count"], item.get("visit_count", 0))
                if item.get("first_diagnosis_date") and item["first_diagnosis_date"] < m.get("first_diagnosis_date", "2099-12-31"):
                    m["first_diagnosis_date"] = item["first_diagnosis_date"]
                m["med_days"] = max(m["med_days"], item.get("med_days", 0))
                weight_order = {"critical": 4, "high": 3, "mid": 2, "low": 1}
                if weight_order.get(item.get("weight", "low"), 0) > weight_order.get(m["weight"], 0):
                    m["weight"] = item.get("weight", "mid")
                if item.get("hospital") and item["hospital"] not in m["hospitals"]:
                    m["hospitals"].append(item["hospital"])

    # 문항별 기간 매핑 (disease_stats에서 직접 조회할 때 사용)
    if product_type == "간편심사 (유병자 3-5-5 기준)":
        _q_since = {"Q1": _d3m_dt, "Q2": _d10y_dt, "Q3": _d5y_dt}
    else:
        _q_since = {"Q1": _d3m_dt, "Q2": _d3m_dt, "Q3": _d1y_dt, "Q4": _d10y_dt, "Q5": _d5y_dt}

    for merge_key, m in merged_items.items():
        code_key = m["code"]
        q        = m["duty_question"]
        flagged_codes.add(code_key)

        if product_type == "건강체/표준체 (일반심사)":
            q_map = {
                "Q1": "[1번질문] 3개월 이내 의료행위",
                "Q2": "[2번질문] 3개월 이내 혈압강하제 등 상시 복용",
                "Q3": "[3번질문] 1년 이내 추가검사(재검사)",
                "Q4": "[4번질문] 10년 이내 입원/수술/7일이상치료/30일이상투약",
                "Q5": "[5번질문] 5년 이내 중증질환",
            }
        else:
            q_map = {
                "Q1": "[간편1번질문] 3개월 이내 진단/소견",
                "Q2": "[간편2번질문] 10년 이내 입원/수술",
                "Q3": "[간편3번질문] 5년 이내 6대 중증 질환",
            }
        q_title = q_map.get(q, f"[{q}번질문]")

        surgery_count = len(set(m["surgery_dates"])) if m["is_surgery"] else 0

        # ── disease_stats에서 직접 조회하여 정확한 값 계산 ──
        # 병원 무관, 동일 질병코드 기준으로 모든 수치 확정
        _ds = disease_stats.get(code_key)
        since_dt = _q_since.get(q, _d10y_dt)

        if _ds:
            # 전체 날짜 (visit + inpatient + surgery) 에서 기간 내 최초/최종 계산
            _all_dates = _ds.get("visit_dates", set()) | _ds.get("inpatient_dates", set()) | _ds.get("surgery_dates", set())
            _all_in_range = _dts_in_range(_all_dates, since_dt)
            first_date  = _all_in_range[0]  if _all_in_range else ""
            latest_date = _all_in_range[-1] if _all_in_range else ""

            # 최초진단일: disease_stats.first_date (전체 기간, 병원 무관)
            _fd = _ds.get("first_date", "2099-12-31")
            first_diagnosis_date = _fd if _fd and _fd != "2099-12-31" else first_date

            # 입원일수: 기본진료 내원일수 합산 (해당 문항 기간)
            _ds_inp_dates = _dts_in_range(_ds.get("inpatient_dates", set()), since_dt)
            _ds_inp_map   = _ds.get("_inpatient_days_map", {})
            ds_inpatient_days  = sum(_ds_inp_map.get(d, 1) for d in _ds_inp_dates) if _ds_inp_dates else 0
            # 입원횟수: 해당 기간 내 입원 날짜 수
            ds_inpatient_count = len(_ds_inp_dates)
            # 통원횟수: 기본진료 외래만 (해당 문항 기간)
            ds_visit_count = len(_dts_in_range(_ds.get("visit_dates", set()), since_dt))
            # 투약일수: 처방조제에서만
            ds_med_days = _max_presc(_ds.get("med_dates_pharma", {}), since_dt)
        else:
            dates_sorted = sorted([d for d in m["dates"] if d])
            first_date    = dates_sorted[0]  if dates_sorted else ""
            latest_date   = dates_sorted[-1] if dates_sorted else ""
            first_diagnosis_date = first_date
            ds_inpatient_days  = m["inpatient_days"]
            ds_inpatient_count = m.get("inpatient_count", 0)
            ds_visit_count     = m.get("visit_count", 0)
            ds_med_days        = m["med_days"]
            _ds_inp_dates      = []

        summary_reports[q_title].append({
            "first_date":           first_date,
            "latest_date":          latest_date,
            "first_diagnosis_date": first_diagnosis_date,
            "code":                 m["code"],
            "name":                 m["name"],
            "visit":                ds_visit_count,
            "med_days":             ds_med_days,
            "inpatient":            ds_inpatient_days,
            "inpatient_count":      ds_inpatient_count,
            "inpatient_dates":      _ds_inp_dates if _ds and _ds_inp_dates else [],
            "surgeries":            {m["surgery_name"]} if m["is_surgery"] and m["surgery_name"] else ({"수술"} if m["is_surgery"] else set()),
            "surgery_dates":        sorted(set(m["surgery_dates"])),
            "hospitals":            m["hospitals"],
            "detail":               m["reason"],
        })

    # ── 메리츠화재 간편보험 예외질환 평가 ──────────────────────────
    meritz_easy_result = evaluate_meritz_easy(disease_stats, today)

    return {
        "ai_result":               ai_result,
        "summary_reports":         {k: list(v) for k, v in summary_reports.items()},
        "flagged_codes":           flagged_codes,
        "prescription_end_details": prescription_end_details,
        "drug_change_summary":     drug_change_summary,
        "analysis_today":          today,
        "parse_errors":            parse_errors,
        "retry_warnings":          retry_warnings,
        "meritz_easy":             meritz_easy_result,
    }
