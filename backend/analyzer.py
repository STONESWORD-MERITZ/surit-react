import asyncio
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
from filters import build_code_based_items as _build_code_based_items, PRODUCT_HEALTH, PRODUCT_EASY

# 비-질병 항목 차단용 (merge 단계 이중 안전망)
_KCD_MERGE_RE = re.compile(r"^[A-Z]\d{2,4}[A-Z0-9]?$")
_NON_DISEASE_NAME_PATTERNS_MERGE = (
    "진찰료", "재진", "초진",
    "조제료", "약국관리료", "약제비",
    "응급및회송료", "외래환자의약품관리료",
    "주사료", "주사기료",
    "검사료", "방사선료", "마취료", "이학요법료",
    "처치및수술", "처치 및수술", "처치및 수 술",
    "재료대", "행위료", "기본진료료", "방문당",
)

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
SURGERY_COST_KEYWORDS      = _KW["surgery_cost_keywords"]
PROCEDURE_KEYWORDS         = _KW["procedure_keywords"]

# 진료비 기반 수술/시술 판정 임계값
SURGERY_COST_THRESHOLD   = 500_000  # 수술 확정 기준 (50만원 이상 + 수술키워드)
PROCEDURE_COST_THRESHOLD = 300_000  # 시술 확정 기준 (30만원 이상 + 시술키워드)

# ── 의학 판단 전용 시스템 프롬프트 ─────────────────────────────
MEDICAL_JUDGMENT_SYSTEM_PROMPT = """당신은 한국 보험 언더라이팅 전문 의사입니다.
설계사가 고객의 알릴의무를 판단할 수 있도록 의학적 관점에서 분석합니다.

판단할 항목:
1. 추가검사/재검사 여부 (1년 이내 알릴의무 Q2)
2. 치료 종결 여부 (3개월 이내 알릴의무 Q1)

반드시 JSON 형식으로만 응답하세요.

[판단 1: 추가검사/재검사 여부]
판단 기준:
- 정기검사, 추적관찰, 건강검진, 모니터링, 단순 스케일링 → false
- 이상소견 후 정밀검사, 재검사, 추가 진단 목적 검사 → true
핵심: 질병코드와 검사 내용의 의학적 연관성 + 정기성 vs 재검사 구분
예) 치주염 정기 스케일링 = false / 종양 의심 후 조직검사 = true

[판단 2: 치료 종결 여부]
판단 기준:
- 일회성 감기, 단순 외상, 종결된 시술 → false (종결됨)
- 만성질환, 재발 가능성, 지속 투약 중 → true (진행 중)
- 수술 후 회복기, 처방약 복약 중 → true (진행 중)
- 처방 종료 후 추가 처방 없음 → false (종결됨)
핵심: 질병코드의 만성/급성 구분 + 마지막 처방 종료일 + 재방문 가능성"""

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
    # 이제 코드는 [영문대분류][숫자...] 형태 (예: K0530, T140, I639)
    # ★ KCD-7 정규화: alpha + 2~5자리 숫자.
    #    K05.30 의 가운데 0 처럼 의미 있는 0은 보존해야 하므로 선행 0을 제거하지 않는다.
    #    OCR 오류로 000이 붙은 경우에만 앞 0을 하나씩 제거한다.
    if len(code) >= 2 and code[0].isalpha() and len(code) > 1:
        alpha = code[0]
        digits = code[1:]
        while digits.startswith("000"):
            digits = digits[1:]
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

    # 1차: 키워드 사전 — 식별성 높은 순(pharma→detail→basic)으로 매칭
    # basic 키워드("진료시작일" 등)는 다른 파일 헤더에도 공통으로 존재하므로 마지막에 확인
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["pharma"]):
        return "pharma"
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["detail"]):
        return "detail"
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["basic"]):
        return "basic"

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


def _detect_ftype_by_page_text(text: str) -> str:
    """PDF 첫 페이지 상단 제목 텍스트로 basic/detail/pharma 판별.
    확실하지 않으면 '' 반환."""
    if not text:
        return ""
    if "기본진료정보" in text:
        return "basic"
    if "세부진료정보" in text:
        return "detail"
    if "처방조제" in text:
        return "pharma"
    return ""


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


def _is_confirmed_surgery_cost_kw(text: str) -> bool:
    """수술 확정 키워드 (비용 기반 판정용) 매칭"""
    if not text:
        return False
    tl = text.lower()
    return any(kw.lower() in tl for kw in SURGERY_COST_KEYWORDS)


def _is_procedure_kw(text: str) -> bool:
    """시술 키워드 매칭 (주사/도수치료/물리치료 등)"""
    if not text:
        return False
    return any(kw in text for kw in PROCEDURE_KEYWORDS)


# 질병명이 아닌 의료수가 청구 항목 키워드 (group_key 생성 필터용)
_BILLING_CODE_KW = (
    "진찰료", "관리료", "기본료", "지도료",
    "처방조제", "약국관리", "의약품관리", "약품관리",
    "방문당", "1일분", "1회당", "회당", "회분",
    "조제기본", "복약지도", "입원료", "처방료",
    "피하또는", "근육내주사", "정맥내주사",
    "악당", "치석제거", "치근활택",
)


def _is_billing_code(name: str) -> bool:
    """의료수가 청구 코드(행위/비용 항목) 여부 판별 — 질병명이면 False."""
    if not name:
        return False
    # [1/3악당] 등 치과 청구 단위 표기
    if "[" in name and ("/" in name or "악당" in name):
        return True
    return any(kw in name for kw in _BILLING_CODE_KW)


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
        "procedures": set(),               # 시술 확정 (30만원이상 + 시술키워드)
        "procedure_dates": set(),          # 시술 날짜
        "surgery_suspected_names": set(),  # 수술 의심 행위명 (50만원이상 + 키워드없음)
        "surgery_suspected_dates": set(),  # 수술 의심 날짜
        "_daily_facts": {},
        "_inpatient_days_map": {},   # date → max(내원일수) per inpatient record
        "chojin_count": 0,           # 세부진료 초진 행위 횟수
        "jaejin_count": 0,           # 세부진료 재진 행위 횟수
        "drug_change_in_3m": False,  # 3개월 내 약 변경/추가/용량증가 여부
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


def parse_single_pdf(uploaded_file, birthdate_pw) -> dict:
    """PDF 1개 파싱. pdfplumber 동기 I/O."""
    fname = getattr(uploaded_file, "name", None) or getattr(uploaded_file, "filename", None) or "unknown.pdf"
    file_recs: list = []
    parse_errors_local: list = []
    pdf_data = uploaded_file.read()
    try:
        with _open_pdf(pdf_data, birthdate_pw or "") as pdf:
            first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
            is_nhis = "건강보험 요양급여내역" in first_text
            # PDF 첫 페이지 상단 제목으로 파일 종류 판별 (헤더 감지 보조)
            page_ftype = _detect_ftype_by_page_text(first_text)

            if is_nhis:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if "건강보험 요양급여내역" in page_text:
                        recs = parse_nhis_text(page_text, fname)
                        file_recs.extend(recs)
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
                        header_ftype = detect_file_type(tuple(headers))
                        # 헤더 감지 성공 우선, unknown이면 페이지 제목 텍스트로 보완
                        ftype = header_ftype if header_ftype != "unknown" else (page_ftype or "unknown")
                        for row in table[1:]:
                            if not any(row):
                                continue
                            if "순번" in str(row[0]):
                                continue
                            rec = {h: str(v).replace("\n", " ").strip() if v else "" for h, v in zip(headers, row)}
                            rec["_ftype"] = ftype
                            rec["_fname"] = fname
                            file_recs.append(rec)
                    del tables
    except ValueError as e:
        parse_errors_local.append(f"🔒 {fname}: {e}")
    except Exception as e:
        err_str = str(e)
        if "password" in err_str.lower() or "encrypted" in err_str.lower():
            parse_errors_local.append(f"🔒 {fname}: 비밀번호가 걸린 PDF입니다. 생년월일을 입력해 주세요.")
        elif "pdf" in err_str.lower() or "syntax" in err_str.lower():
            parse_errors_local.append(f"⚠️ {fname}: 손상되었거나 지원하지 않는 PDF 형식입니다.")
        else:
            parse_errors_local.append(f"⚠️ {fname}: 파일 읽기 실패 — {err_str[:80]}")
    finally:
        del pdf_data
        gc.collect()
    return {"filename": fname, "records": file_recs, "parse_errors": parse_errors_local}


def _finalize_raw_text_for_gemini(
    filtered_lines: list[str],
    visit_count_lines: list[str],
    cross_surgery_hints: list[str],
    first_diag_lines: list[str],
    drug_change_text: str,
    presc_end_text: str,
) -> str:
    raw_text = "\n".join(filtered_lines[:800])
    if visit_count_lines:
        raw_text = "[10년내 질병코드별 통원횟수 집계 — Q4 7회이상통원 판단 기준]\n" \
                   + "\n".join(visit_count_lines) + "\n\n" + raw_text
    if cross_surgery_hints:
        raw_text = "[기본/세부 동일일자 교차검증 — 수술 추정 근거]\n" \
                   + "\n".join(f"- {h}" for h in cross_surgery_hints[:80]) + "\n\n" + raw_text
    if first_diag_lines:
        raw_text = "[질병별 최초·최종 진단일 — 고지사항 최초진단일 확인]\n" \
                   + "\n".join(first_diag_lines[:100]) + "\n\n" + raw_text
    if drug_change_text:
        raw_text = drug_change_text + "\n" + raw_text
    if presc_end_text:
        raw_text = presc_end_text + "\n" + raw_text
    MAX_RAW_TEXT_LEN = 30_000
    if len(raw_text) > MAX_RAW_TEXT_LEN:
        raw_text = raw_text[:MAX_RAW_TEXT_LEN] + "\n... (truncated)"
    return raw_text


def _worst_insurance_verdict(*vals: str) -> str:
    prio = {"불가": 3, "조건부": 2, "가능": 1}
    best = ""
    bp = 0
    for v in vals:
        if not v or not isinstance(v, str):
            continue
        vv = v.strip()
        p = prio.get(vv, 0)
        if p > bp:
            bp = p
            best = vv
    return best or "가능"


def _merge_ai_results(parts: list[dict]) -> dict:
    if not parts:
        raise AnalysisError("AI 분석 결과가 없습니다.")
    merged: dict = {
        "flagged_items": [],
        "exempt_items": [],
        "drug_change_hit": False,
        "drug_change_reason": "",
        "total_flagged": 0,
    }
    hit_bool_keys = [
        "q1_hit", "q2_hit", "q3_hit", "q4_hit",
        "simple_q1_hit", "simple_q2_hit", "simple_q3_hit",
    ]
    reason_join_keys = [
        "q1_reason", "q2_reason", "q3_reason", "q4_reason",
        "simple_q1_reason", "simple_q2_reason",
    ]
    for p in parts:
        merged["flagged_items"].extend(p.get("flagged_items") or [])
        merged["exempt_items"].extend(p.get("exempt_items") or [])
        if p.get("drug_change_hit"):
            merged["drug_change_hit"] = True

    for k in hit_bool_keys:
        merged[k] = any(bool(x.get(k)) for x in parts)

    for k in reason_join_keys:
        texts = [x.get(k) for x in parts if x.get(k)]
        merged[k] = "; ".join(texts) if texts else ""

    dcr = [x.get("drug_change_reason") for x in parts if x.get("drug_change_reason")]
    merged["drug_change_reason"] = "; ".join(dcr) if dcr else ""

    sq3 = None
    for x in parts:
        v = x.get("simple_q3_disease")
        if v:
            sq3 = v
            break
    merged["simple_q3_disease"] = sq3

    merged["health_verdict"] = _worst_insurance_verdict(*(x.get("health_verdict") or "" for x in parts))
    hr = [x.get("health_reason") for x in parts if x.get("health_reason")]
    merged["health_reason"] = "; ".join(hr) if hr else ""

    merged["simple_verdict"] = _worst_insurance_verdict(*(x.get("simple_verdict") or "" for x in parts))
    sr = [x.get("simple_reason") for x in parts if x.get("simple_reason")]
    merged["simple_reason"] = "; ".join(sr) if sr else ""

    rec = [x.get("recommend") for x in parts if x.get("recommend")]
    merged["recommend"] = "; ".join(rec) if rec else ""

    summ = [x.get("summary") for x in parts if x.get("summary")]
    merged["summary"] = "\n".join(summ) if summ else ""

    merged["total_flagged"] = len(merged["flagged_items"])
    return merged


async def _call_medical_judgment(
    type1_items: list[dict],
    type2_items: list[dict],
    api_key: str,
) -> dict:
    """추가검사/재검사 + 치료 종결 여부를 단일 Gemini 배치 호출로 판단.

    Returns:
        {
            "additional_tests": {"disease_code": {is_additional_test, test_type, reason}},
            "treatment_ongoing": {"disease_code": {is_ongoing, reason}},
        }
    """
    if not type1_items and not type2_items:
        return {"additional_tests": {}, "treatment_ongoing": {}}

    parts = []
    if type1_items:
        parts.append(
            "[추가검사/재검사 판단 목록]\n"
            + json.dumps(type1_items, ensure_ascii=False, indent=2)
        )
    if type2_items:
        parts.append(
            "[치료 종결 여부 판단 목록]\n"
            + json.dumps(type2_items, ensure_ascii=False, indent=2)
        )

    contents = "\n\n".join(parts) + """

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON:
{
  "additional_tests": [
    {"disease_code": "코드", "is_additional_test": true또는false, "test_type": "재검사 또는 정기검사", "reason": "판단 근거"}
  ],
  "treatment_ongoing": [
    {"disease_code": "코드", "is_ongoing": true또는false, "reason": "판단 근거"}
  ]
}"""

    try:
        api_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=120_000),
        )
    except TypeError:
        api_client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(system_instruction=MEDICAL_JUDGMENT_SYSTEM_PROMPT)

    def _sync_gen():
        return api_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=config,
        )

    try:
        if hasattr(api_client, "aio") and hasattr(api_client.aio.models, "generate_content"):
            message = await api_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=config,
            )
        else:
            message = await asyncio.to_thread(_sync_gen)

        raw = message.text if getattr(message, "text", None) else ""
        if not raw.strip():
            return {"additional_tests": {}, "treatment_ongoing": {}}

        result = extract_json(raw)
        at_out = {
            item["disease_code"]: item
            for item in result.get("additional_tests", [])
            if isinstance(item, dict) and "disease_code" in item
        }
        to_out = {
            item["disease_code"]: item
            for item in result.get("treatment_ongoing", [])
            if isinstance(item, dict) and "disease_code" in item
        }
        return {"additional_tests": at_out, "treatment_ongoing": to_out}
    except Exception as e:
        # 비치명적 오류 — 메인 분석은 계속 진행
        return {"additional_tests": {}, "treatment_ongoing": {}, "_error": str(e)[:120]}


async def analyze_single_pdf(parsed_data: dict, product_type: str, reference_date, api_key: str) -> dict:
    """파싱된 PDF 1건에 대해 Gemini 분석 (비동기)."""
    _ = reference_date
    fname = parsed_data["filename"]
    today_str = parsed_data["today_str"]
    raw_text = parsed_data["raw_text"]
    system_prompt = parsed_data["system_prompt"]
    retry_local: list[str] = []

    GEMINI_TIMEOUT_SECONDS = 240
    try:
        api_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
        )
    except TypeError:
        api_client = genai.Client(api_key=api_key)

    ai_result = None
    last_error = None
    raw_response = ""
    MAX_RETRIES = 5
    RETRY_DELAYS = [5, 10, 20, 40, 60]
    contents = f"고객 기준일: {today_str}\n심사 유형: {product_type}\n\n진료 데이터:\n{raw_text}"
    config = types.GenerateContentConfig(system_instruction=system_prompt)

    def _sync_generate():
        return api_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=config,
        )

    for attempt in range(MAX_RETRIES):
        try:
            if hasattr(api_client, "aio") and hasattr(api_client.aio.models, "generate_content"):
                message = await api_client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=config,
                )
            else:
                message = await asyncio.to_thread(_sync_generate)
            raw_response = message.text if getattr(message, "text", None) else ""
            if not raw_response.strip():
                raise ValueError("AI 응답이 비어있습니다.")
            ai_result = extract_json(raw_response)
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                continue
            return {
                "filename": fname,
                "ai_result": None,
                "retry_warnings": retry_local,
                "error": f"AI 응답 파싱 오류: {e}",
                "raw_response_snip": raw_response[:800],
            }
        except Exception as e:
            err_str = str(e)
            if ("503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str) \
                    and attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAYS[attempt]
                retry_local.append(
                    f"[{fname}] Gemini 서버 과부하로 {wait}초 후 재시도합니다... ({attempt + 1}/{MAX_RETRIES - 1})"
                )
                await asyncio.sleep(wait)
                continue
            return {"filename": fname, "ai_result": None, "retry_warnings": retry_local, "error": str(e)}

    if ai_result is None:
        return {
            "filename": fname,
            "ai_result": None,
            "retry_warnings": retry_local,
            "error": str(last_error),
            "raw_response_snip": raw_response[:800] if raw_response else "",
        }
    return {"filename": fname, "ai_result": ai_result, "retry_warnings": retry_local, "error": None}


# ==========================================
# 분석 엔진
# ==========================================
async def run_analysis(active_files, product_type, reference_date, birthdate_pw, api_key) -> dict:
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
    _d3m_dt  = today - timedelta(days=90)
    _d1y_dt  = today - timedelta(days=365)
    _d5y_dt  = today - timedelta(days=1825)
    _d10y_dt = today - timedelta(days=3650)
    all_records = []
    parse_errors = []
    retry_warnings = []

    # ── PDF 파싱 (병렬 스레드 — pdfplumber 동기) ──────────────────
    parse_results = await asyncio.gather(
        *[asyncio.to_thread(parse_single_pdf, uf, birthdate_pw) for uf in active_files],
        return_exceptions=True,
    )
    for i, pr in enumerate(parse_results):
        uf = active_files[i]
        fn = getattr(uf, "name", None) or getattr(uf, "filename", None) or f"file_{i}"
        if isinstance(pr, BaseException):
            parse_errors.append(f"⚠️ {fn}: PDF 파싱 중 예외 — {str(pr)[:120]}")
            continue
        all_records.extend(pr["records"])
        parse_errors.extend(pr["parse_errors"])

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
        "has_detail_proc_kw": False,
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
        # 상병코드 추출 — "주상병" 단독 키는 "주상병코드" 컬럼과 부분일치하므로 절대 사용 금지
        if ftype == "pharma":
            raw_code = ""
        else:
            # 1순위: 주상병 명시 컬럼
            raw_code = get_val(row, ["주상병코드", "주상병기호"])
            # 2순위: 일반 상병코드
            if not raw_code:
                raw_code = get_val(row, ["상병코드", "진단코드"])
            # 3순위: 단일 "코드" 컬럼 (가장 광범위 — 마지막 시도)
            if not raw_code:
                raw_code = get_val(row, ["코드"])
        code_str = normalize_code(raw_code)

        # 상병명/행위명 추출
        # "주상병" 단독 키는 "주상병코드" 컬럼 값이 들어오므로 반드시 제외
        if ftype == "detail":
            name_str = get_val(row, ["행위명칭", "행위명", "진료내역", "처치및수술", "처치및수 술"])
        elif ftype == "pharma":
            name_str = get_val(row, ["약품명", "의약품명"])
        else:  # basic, unknown, nhis
            name_str = get_val(row, ["주상병명", "상병명", "약품명", "진료내역",
                                     "행위명칭", "행위명", "처치및수술", "처치및수 술"])

        in_out   = get_val(row, ["입내원구분", "입원외래구분", "입원", "외래", "구분"])
        hospital = get_val(row, ["병·의원", "기관명", "요양기관명"])
        date_str = get_val(row, ["진료개시일", "진료시작일", "진료일", "조제일자", "처방일"])
        m_days_raw = get_val(row, ["내원일수", "투약일수", "요양일수"])
        m_days = int(re.findall(r"\d+", m_days_raw)[0]) if re.findall(r"\d+", m_days_raw) else 0
        cost_raw = get_val(row, ["총진료비", "진료비", "총 진료비", "본인부담총액", "급여비용총액"])
        cost_val = _to_int_cost(cost_raw)

        if code_str:
            group_key = code_str
        elif ftype == "pharma":
            # 처방조제: 약품명+월로 임시 group (filters에서 KCD 미보유로 자동 스킵됨,
            # 약 변경/투약일수 집계용으로만 사용)
            name_norm    = re.sub(r"[\s\d\.\-\[\]]", "", name_str)[:12]
            month_bucket = parse_date(date_str)[:7] if parse_date(date_str) else ""
            group_key = f"PHARMA|{name_norm}|{month_bucket}" if name_norm else ""
        else:
            # 기본진료/세부진료에서 상병코드 없는 행 → 새 disease entry 생성 금지
            # (세부진료 행위명, 진찰료 등 비-질병 청구항목은 disease_stats에 직접 반영 안 함)
            group_key = ""
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
                # 기본진료정보: 약국 입내원구분 행 제외 (병의원 진료만 인정)
                if "약국" in in_out:
                    continue
                is_inpatient = "입원" in in_out or "입원" in name_str
                if is_inpatient:
                    s["inpatient_dates"].add(clean_date)
                    if m_days > 0:
                        prev_inp = s["_inpatient_days_map"].get(clean_date, 0)
                        s["_inpatient_days_map"][clean_date] = max(prev_inp, m_days)
                    elif clean_date not in s["_inpatient_days_map"]:
                        # 내원일수 0 = 퇴원일 기록 — 일수 0으로 마킹 (기본값 1 적용 방지)
                        s["_inpatient_days_map"][clean_date] = 0
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
                # 초진/재진 카운트 (세부진료 행위명 기준)
                _chk = act_name or name_str
                if "초진" in _chk:
                    s["chojin_count"] += 1
                elif "재진" in _chk:
                    s["jaejin_count"] += 1
            elif ftype == "pharma":
                # 처방조제: 처방 행만 사용 — 조제 행 제외
                _gubun = get_val(row, ["구분", "처방조제구분", "처방구분", "분류"])
                if _gubun and "조제" in _gubun and "처방" not in _gubun:
                    continue

                # ★ 같은 날짜의 기본진료 disease entry에 투약일수/약품명 부착
                # 처방조제는 KCD 코드가 없으므로, 동일 날짜 visit/inpatient 가진 disease 탐색
                _target_groups = []
                for _ck, _cs in disease_stats.items():
                    if not _cs.get("diag_code") or _ck.startswith("PHARMA|"):
                        continue
                    if clean_date in _cs.get("visit_dates", set()) or \
                       clean_date in _cs.get("inpatient_dates", set()):
                        _target_groups.append(_ck)

                if _target_groups:
                    # 매칭된 disease 모두에 투약 정보 부착
                    for _tg in _target_groups:
                        _ts = disease_stats[_tg]
                        _ts["has_pharma"] = True
                        if m_days > 0:
                            _prev = _ts["med_dates_pharma"].get(clean_date, 0)
                            if m_days > _prev:
                                _ts["med_dates_pharma"][clean_date] = m_days
                        _drug = name_str.strip()
                        if _drug:
                            if days_ago <= 90:
                                _ts["drug_names_in_90"].add(_drug)
                            else:
                                _ts["drug_names_before_90"].add(_drug)
                    continue  # 매칭 완료 — PHARMA 임시 entry는 건너뜀

                # 매칭 없음 → PHARMA 임시 그룹에 부착 (filters에서 KCD 미보유로 자동 스킵됨)
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
                    if _is_procedure_kw(target_idx):
                        idx["has_detail_proc_kw"] = True

        if hospital and "약국" not in hospital and ftype != "pharma":
            s["hospitals"].add(hospital)
        # 질병명은 기본진료/nhis 에서만 설정 — 세부진료 행위명·약품명으로 덮지 않음
        if name_str and not s["name"] and ftype not in ("detail", "pharma"):
            s["name"] = name_str

    # ── 기본진료+세부진료 동일일자 교차 수술/시술 판정 ──────────────
    # 규칙:
    #   컬럼확정(처치및수술 컬럼 값 있음) → 수술 확정 (비용 무관)
    #   50만원 이상 + 수술키워드            → 수술 확정
    #   50만원 이상 + 키워드 없음           → 수술 의심 (설계사 확인 유도)
    #   30만원 이상 + 시술키워드            → 시술 확정
    #   30만원 이상 + 수술키워드            → AI 힌트 전달
    #   30만원 미만                          → 일반 외래 (제외)
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
            has_detail_proc    = bool(idx.get("detail_proc_names"))
            has_detail_surg_kw = bool(idx.get("has_detail_surg_kw"))
            has_detail_proc_kw = bool(idx.get("has_detail_proc_kw"))
            # ★ 세부진료 "처치및수술" 컬럼으로 확정된 경우 — 비용 무관 수술 확정
            is_col_confirmed = day_fact.get("_is_surg_by_column", False)

            if is_col_confirmed:
                # 컬럼값으로 이미 수술 확정 — 교차확인 기록만
                if d not in _s["surgery_dates"]:
                    _s["surgery_dates"].add(d)
                    if idx["detail_proc_names"]:
                        _s["surgeries"].update(idx["detail_proc_names"])
                cross_surgery_hints.append(
                    f"{d} {_dc or ckey} {'|'.join(list(idx.get('detail_proc_names', set()))[:2]) or _name} "
                    f"컬럼확정(처치및수술+기본진료비 {max_cost:,}원)"
                )

            elif max_cost >= SURGERY_COST_THRESHOLD:  # 50만원 이상
                if has_detail_surg_kw:
                    # 수술 확정
                    if d not in _s["surgery_dates"]:
                        _s["surgery_dates"].add(d)
                    if idx["detail_proc_names"]:
                        # 수술 확정 키워드가 포함된 행위명만 등록
                        for pn in idx["detail_proc_names"]:
                            if _is_confirmed_surgery_cost_kw(pn) or _is_surgery_match(pn):
                                _s["surgeries"].add(pn)
                        if not (_s["surgeries"] & set(idx["detail_proc_names"])):
                            _s["surgeries"].update(idx["detail_proc_names"])
                        _hint_name = next(iter(idx["detail_proc_names"]))
                    else:
                        _hint_name = _name or _dc or "수술"
                    cross_surgery_hints.append(
                        f"{d} {_dc or ckey} {_hint_name} 교차확정(수술키워드+기본진료비 {max_cost:,}원)"
                    )
                elif has_detail_proc:
                    # 50만원 이상이지만 수술 키워드 없음 → 수술 의심
                    _hint_name = next(iter(idx["detail_proc_names"]), _name or "수술 의심")
                    _s["surgery_suspected_names"].add(_hint_name)
                    _s["surgery_suspected_dates"].add(d)
                    cross_surgery_hints.append(
                        f"{d} {_dc or ckey} {_hint_name} 수술의심(키워드없음+기본진료비 {max_cost:,}원) ★설계사확인"
                    )

            elif max_cost >= PROCEDURE_COST_THRESHOLD:  # 30만원 이상 50만원 미만
                if has_detail_proc_kw:
                    # 시술 확정
                    for pn in (idx.get("detail_proc_names") or set()):
                        if _is_procedure_kw(pn):
                            _s["procedures"].add(pn)
                    _s["procedure_dates"].add(d)
                elif has_detail_surg_kw:
                    # 수술 키워드 있지만 50만원 미만 → AI 힌트 전달
                    _hint_name = next(iter(idx["detail_proc_names"])) if idx["detail_proc_names"] else (_name or _dc or "진료")
                    cross_surgery_hints.append(
                        f"{d} {_dc or ckey} {_hint_name} 교차후보(수술키워드+기본진료비 {max_cost:,}원) ★AI판단필요"
                    )
            # else: 30만원 미만 → 일반 외래, 수술/시술 판정 제외

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

    # ── 코드 기반 결정론적 알릴의무 (filters.py 위임) ──────────────
    # code_based_items는 drug_change_summary 계산 후 아래에서 생성됨
    # (drug_change_groups 를 filters.py로 전달하기 위해 순서 조정)

    # ── AI 전달용 raw_text 구축 ───────────────────────────────────
    raw_entries = []
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
        if ftype == "detail":
            name_str = get_val(row, ["행위명칭", "행위명", "진료내역", "처치및수술"])
        elif ftype == "pharma":
            name_str = get_val(row, ["약품명", "의약품명"])
        else:
            name_str = (
                get_val(row, ["상병명", "주상병명", "상병기호"])
                or get_val(row, ["진료내역", "행위명"])
            )
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

        fname_row = str(row.get("_fname", "") or "")

        inpatient_flag = "입원" if "입원" in in_out else ""
        line_date = parse_date(date_str) or date_str

        act_suffix = ""
        if ftype == "detail":
            _act = get_val(row, ["행위명칭", "행위명", "진료내역", "처치"])
            if _act:
                act_suffix = f" 행위:{_act[:25]}"
        line_core = (
            f"{line_date} [{ftype}] {code_str} {display_name}{act_suffix} {hospital[:10]}"
            + (f" 투약{m_days}일" if m_days and m_days != "0" else "")
            + (f" 진료비{cost_raw}" if cost_raw else "")
            + (f" {inpatient_flag}" if inpatient_flag else "")
        )
        raw_entries.append((fname_row, line_core))

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
                # disease_stats에 3개월 내 약 변경 플래그 설정
                disease_stats[group_key]["drug_change_in_3m"] = True

    # ── 코드 기반 결정론적 알릴의무 (filters.py 위임) ──────────────
    drug_change_groups = {
        dc["group"] for dc in drug_change_summary
        if dc.get("change_type") in ("약 종류 변경", "새 약 추가", "용량 증가")
    }
    code_based_items = _build_code_based_items(
        disease_stats=disease_stats,
        reference_date=today,
        product_type=product_type,
        drug_change_groups=drug_change_groups,
    )

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
    filtered_entries = []
    for fname_row, line in raw_entries:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
        if not date_match:
            filtered_entries.append((fname_row, line))
            continue
        line_date = date_match.group(1)
        try:
            dt = datetime.strptime(line_date, "%Y-%m-%d")
        except ValueError:
            filtered_entries.append((fname_row, line))
            continue
        days_ago = (today - dt).days
        if days_ago < 0 or days_ago > 3650:
            continue
        tags = []
        if days_ago <= 90:   tags.append("IN_3M")
        if days_ago <= 365:  tags.append("IN_1Y")
        if days_ago <= 1825: tags.append("IN_5Y")
        if days_ago <= 3650: tags.append("IN_10Y")
        filtered_entries.append((fname_row, line + " [" + ",".join(tags) + "]"))

    filtered_lines = [t[1] for t in filtered_entries]
    lines_by_file = defaultdict(list)
    for fname_row, tl in filtered_entries:
        if fname_row:
            lines_by_file[fname_row].append(tl)

    # ── 통원횟수·처방일수 집계 ───────────────────────────────────
    visit_count_lines = []
    for _code, _s in disease_stats.items():
        _visits_in_10y = []
        for _d in _s["visit_dates"]:
            try:
                if datetime.strptime(_d, "%Y-%m-%d") >= _d10y_dt:
                    _visits_in_10y.append(_d)
            except ValueError:
                pass
        _med_dict = _s["med_dates_pharma"] if _s.get("has_pharma") and _s["med_dates_pharma"] else _s["med_dates_basic"]
        _max_presc_days = 0
        for _pd, _pv in _med_dict.items():
            try:
                if datetime.strptime(_pd, "%Y-%m-%d") >= _d10y_dt:
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

    # ── 최초 진단일 정보 (동일코드 기준) ────────────────────────────
    first_diag_lines = []
    for _ck, _s in disease_stats.items():
        _fd = _s.get("first_date", "2099-12-31")
        if _fd and _fd != "2099-12-31":
            _dc = _s.get("diag_code") or _ck
            _nm = _s.get("name", "")[:20]
            first_diag_lines.append(f"  {_dc} {_nm} 최초={_fd} 최종={_s.get('latest_date','')}")

    # ── 프롬프트 구성 ─────────────────────────────────────────────
    if product_type == "건강체/표준체 (일반심사)":
        criteria_text = f"""
[건강체/표준체 알릴의무 4문항] (기준일: {today_str})
Q1. 최근 3개월({d_3m} 이후) — 태그 [IN_3M] 항목만: 아래 중 하나라도 해당 시 고지
    ① 질병확정진단 / 의심소견 / 추가검사 필요소견
    ② 입원
    ③ 수술 (제왕절개 포함)
    ④ 투약 (의사 처방만, 약국 자가구매 제외)
    ⑤ 마약·혈압강하제·신경안정제·수면제·각성제·흥분제·진통제 상시 복용
Q2. 최근 1년({d_1y} 이후) — 태그 [IN_1Y] 항목만: 의사 진찰·검사 후 추가검사(재검사) 받은 사실
    ★ Q2 추가검사(재검사) 정확한 정의:
       [해당 O] 진찰 결과 이상소견이 확인되어 더 정확한 진단을 위해 시행한 추가 검사
               예) X-RAY 촬영 후 이상소견 → MRI·CT·혈액검사 등 추가 시행
       [해당 X — 반드시 Q2 면제] 아래 경우는 절대 Q2 배정 불가:
               - 정기검사·추적관찰 (치료 없이 유지 상태에서 주기적으로 시행)
               - 단순 1회 검사만 시행하고 종결 (이상소견 없는 경우)
               - 검사 후 추가 검사 없이 단순 치료로만 이어진 경우 → Q2 아닌 Q1/Q3로 판단
Q3. 최근 10년({d_10y} 이후) — 태그 [IN_10Y] 항목만: 아래 중 하나라도 해당 시 고지
    - 입원
    - 수술 (제왕절개 포함)
    - 동일질병 계속하여 7일 이상 치료 ★ = 동일 KCD코드 기준 통원횟수 7회 이상
    - 동일질병 계속하여 30일 이상 투약 (단일 처방 30일 이상 OR 만성질환 매월 지속 처방)
Q4. 최근 5년({d_5y} 이후) — 태그 [IN_5Y] 항목만: 아래 중대질병 확정진단만 해당
    ① 암 (악성신생물): C00~C97, D00~D09
    ② 백혈병: C91~C95 (암 포함)
    ③ 고혈압: I10~I15
    ④ 협심증: I20
    ⑤ 심근경색: I21~I22
    ⑥ 심장판막증: I05~I09, I34~I38
    ⑦ 간경화증: K74
    ⑧ 뇌출혈: I60~I62
    ⑨ 뇌경색: I63~I64
    ⑩ 당뇨병: E10~E14
    ⑪ 에이즈: B20~B24
    ★ Q4 면제: 위 코드 범위에 해당하지 않는 모든 질환 → Q4 배정 불가"""
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
Q3. 최근 5년({d_5y} 이후) — 태그 [IN_5Y] 항목만: 아래 중대질병 확정진단만 해당
    ① 암: C00~C97, D00~D09
    ② 뇌출혈: I60~I62
    ③ 뇌경색: I63~I64
    ④ 협심증: I20
    ⑤ 심근경색: I21~I22
    ⑥ 심장판막증: I05~I09, I34~I38
    ⑦ 간경화: K74

    ★ Q3 절대 면제 (아무리 심해도 Q3 배정 불가):
    - 당뇨병 (E10~E14 계열) → 간편심사 Q3 해당 아님
    - 고혈압 (I10~I15) → Q3 해당 아님
    - 무릎관절증·척추협착 등 근골격계 → Q3 해당 아님
    - 만성신부전·갑상선·고지혈증 등 → Q3 해당 아님
    - 위/대장 용종 → Q3 해당 아님
    - 위 KCD 코드 범위 외 모든 질환 → Q3 배정 절대 불가

[면제] 통원횟수 7회 미만인 경우 / 30일 미만 단순 투약 / 중대질병 KCD 코드 외 모든 질환
[약 변경 면제] 3개월 이전부터 동일 약 지속 복용(변경 없음) → 면제 / 동일 약 용량만 감소 → 면제"""

    is_health = product_type == "건강체/표준체 (일반심사)"
    step2_tag_rules = (
        "건강체/표준체 기준:\n"
        "- [IN_3M] 있어야만 → Q1 배정 가능\n"
        "- [IN_1Y] 있어야만 → Q2 배정 가능\n"
        "- [IN_10Y] 있어야만 → Q3 배정 가능\n"
        "- [IN_5Y] 있어야만 → Q4 배정 가능\n"
        "- [IN_3M] 없으면 → Q1 배정 절대 불가\n"
        "- [IN_10Y]만 있고 [IN_3M] 없으면 → Q3만 배정 (Q1 절대 불가)\n"
        "★ 사용 가능한 질문번호: Q1, Q2, Q3, Q4 뿐. Q5는 절대 사용 금지.\n"
        "  Q1=3개월(진단·투약·특정약물), Q2=1년(추가검사), Q3=10년(입원/수술/7회이상/30일이상), Q4=5년(중대질병)"
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
[4단계: Q3 수술 인정 목록 — 반드시 is_surgery=true]
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
▶ Q3 반드시 면제 처리 항목:
  ① 동일 질병코드 통원횟수 6회 이하 (7회 미만), 투약 30일 미만, 입원 없음, 수술 없음
     ★ "계속하여 7일 이상 치료"는 처방일수가 아닌 통원횟수 기준 — [통원집계]에서 해당 코드 통원횟수가 7회 미만이면 반드시 면제
     ★★ 처방일수 7일 이상이라도 통원횟수 7회 미만이면 "7일 이상 치료" 해당 아님
     ★★★ 이 규칙은 정신건강의학과(F계열)·신경과 포함 모든 진료과에 동일하게 적용
        정신건강의학과 1회 방문 + 투약 30일 미만 → Q3 절대 면제 (weight=high여도 면제)
  ② 단순 감기·비염·인후염·결막염·두드러기·타박상·염좌 (통원횟수 무관하게 Q3 면제)
  ③ 치과 스케일링·단순 충치 보존치료 (발치·임플란트 제외)
  ④ 한방 단순 침구치료 (수술/입원 미동반)
  ⑤ 단순 통원 검사만 받고 종결 (수술/입원/통원7회이상 치료 없음)
  ⑥ 방광염·요로감염 단순 항생제 투약 (1회성)
  ⑦ 알레르기성 피부염 단순 외래 1~2회
  ⑧ 정신건강의학과·신경과·심리검사 단순 1회 방문 (통원 7회 미만, 입원 없음, 투약 30일 미만) → Q3 면제

★★ 질병코드 원칙: 질병코드(KCD)는 반드시 기본진료에서 확인된 코드만 사용.
   처방조제(약품명)로부터 질병코드를 추정/예측하지 마세요.
   처방조제 데이터는 투약일수·약 변경 판단에만 사용합니다.

▶ 만성질환 30일이상 투약 판단:
  - 당뇨(E11계열): 매월 지속 처방 확인 시 → med_days=365, Q3 해당 (Q2 아님)
  - 고혈압(I10계열): 매월 지속 처방 → med_days=365, Q3 해당 (Q2 아님)
  - 고지혈증(E78계열): 매월 지속 처방 → med_days=365, Q3 해당
  - 갑상선(E03/E05): 매월 지속 처방 → med_days=365, Q3 해당
  - 단, 3개월 이내에만 처방 기록이 있고 이전 기록 없음 → Q1 해당 가능"""

        json_duty_q_values = "Q1 또는 Q2 또는 Q3 또는 Q4 (Q5는 절대 사용 금지)"
        json_hit_fields = """\
  "q1_hit": true또는false, "q1_reason": "진단/입원/수술/투약/특정약물상시복용 중 해당 사유",
  "q2_hit": true또는false, "q2_reason": "추가검사(재검사) 사유 또는 없음",
  "q3_hit": true또는false, "q3_reason": "입원/수술/7회이상통원/30일이상투약 중 해당 사유",
  "q4_hit": true또는false, "q4_reason": "중대질병명 및 KCD코드 또는 없음","""

        step5_q3_health_text = (
            "\n▶ 건강체 Q2 추가검사(재검사) 판단 기준 (★핵심 규칙):\n"
            "  Q2는 '진찰 후 이상소견 → 추가 검사' 두 단계가 반드시 존재해야 함.\n\n"
            "  [Q2 해당 O — 반드시 포함]:\n"
            "  - 진찰 결과 이상소견 발견 → 더 정확한 진단을 위해 추가 검사 시행\n"
            "  - 예: 진찰 후 X-RAY → 이상소견 → MRI/CT/혈액검사/초음파 등 추가 시행\n"
            "  - 추가 검사는 당일이 아니어도 됨 (동일 질병코드로 연결된 경우)\n"
            "  - 검사 결과 이후 치료로 이어졌어도, 이상소견으로 추가 검사를 받은 사실 자체가 Q2\n\n"
            "  [Q2 해당 X — 반드시 면제]:\n"
            "  - 단순 1회 검사만 시행하고 종결 (X-RAY 1회, 혈액검사 1회, 초음파 1회 등 단독)\n"
            "  - 이상소견 없이 단순 확인·스크리닝 목적의 1회 검사\n"
            "  - 정기검사·추적관찰 (치료 없이 병증이 유지되는 상태에서 시행하는 주기적 검사)\n"
            "  - 검사 1종만 찍고 추가 검사 없이 바로 치료로 이어진 경우 → Q1 또는 Q3로만 처리\n"
            "  - 건강검진 항목으로 시행된 검사"
        )
        q3_diabetes_note = "(Q3만)"
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
            "★ 7일 이상 치료, 30일 이상 투약은 간편심사 Q2 해당 없음 (건강체 Q3 기준). Q2에 배정 금지."
        )
        step5_q4_exempt_text = (
            "\n▶ 간편심사 Q2 면제 기준:\n"
            "  - 입원 없음 AND 수술 없음 → Q2 배정 절대 불가 (단순 통원은 Q2 해당 없음)\n"
            "  - 7일 이상 치료·30일 이상 투약 만으로는 Q2 해당 없음 (건강체 Q3 기준임)"
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
[5단계: 추가검사(Q2) 판단 + 면제 — 과잉 고지 방지]
━━━━━━━━━━━━━━━━━━━━━━━━━━
{step5_q3_health_text}

▶ 간편심사 Q3 절대 면제 규칙 (★최우선 적용):
  간편심사 Q3는 아래 KCD 코드 계열만 해당. 나머지는 모두 Q3 배정 절대 불가.
  허용: C00~C97·D00~D09(암) / I60~I62(뇌출혈) / I63~I64(뇌경색) / I20(협심증) / I21~I22(심근경색) / I05~I09·I34~I38(심장판막증) / K74(간경화)

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
- critical: 암(C·D0계열)/뇌졸중(I60-64)/심근경색(I21-22)/협심증(I20)/간경화(K74)/심장판막(I05-09,I34-38)/에이즈(B20-24)/괴사성근막염
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

    # ── 의학 판단 입력 준비 (추가검사/재검사 + 치료 종결) ────────────
    _mj_type1: list[dict] = []   # 추가검사/재검사 판단 대상
    _mj_type2: list[dict] = []   # 치료 종결 판단 대상
    _seen_mj1: set[str] = set()
    _seen_mj2: set[str] = set()

    for _jck, _js in disease_stats.items():
        _jdc = (_js.get("diag_code") or _jck).strip()
        if not _jdc or _jdc in ("$", "해당없음"):
            continue
        _jname   = _js.get("name", "")
        _jlatest = _js.get("latest_date", "")

        # 판단 1: tests_found가 있으면 → 추가검사 여부 판단
        if _js.get("tests_found") and _jdc not in _seen_mj1:
            _seen_mj1.add(_jdc)
            _mj_type1.append({
                "disease_code": _jdc,
                "disease_name": _jname,
                "date":         _jlatest,
                "treatments":   [t[:40] for t in list(_js["tests_found"])[:10]],
            })

        # 판단 2: 마지막 진료일이 3개월 이내
        _jdt = _parse_ymd(_jlatest)
        if _jdt and _jdt >= _d3m_dt and _jdc not in _seen_mj2:
            _seen_mj2.add(_jdc)
            _all_procs: set[str] = set()
            for _df_val in _js.get("_daily_facts", {}).values():
                _all_procs.update(_df_val.get("detail_proc_names", set()))
            _treatments = list(
                (_all_procs | _js.get("tests_found", set()) | _js.get("surgeries", set()))
            )[:15]
            _presc_list: list[dict] = []
            for _pd, _pdays in sorted(_js.get("med_dates_pharma", {}).items(), reverse=True)[:5]:
                _pdt2 = _parse_ymd(_pd)
                if _pdt2 and _pdt2 >= _d3m_dt and _pdays > 0:
                    _presc_list.append({"date": _pd, "days": _pdays})
            _recent_drugs = [d[:30] for d in list(_js.get("drug_names_in_90", set()))[:5]]
            _mj_type2.append({
                "disease_code":  _jdc,
                "disease_name":  _jname,
                "last_date":     _jlatest,
                "today":         today_str,
                "treatments":    [t[:40] for t in _treatments],
                "prescriptions": _presc_list,
                "recent_drugs":  _recent_drugs,
            })

    # ── Gemini API 호출 (PDF별 병렬 + 의학 판단 병렬) ────────────
    gemini_payloads = []
    for uf in active_files:
        fn = getattr(uf, "name", None) or getattr(uf, "filename", None) or "unknown.pdf"
        flines = lines_by_file.get(fn, [])
        rt_part = _finalize_raw_text_for_gemini(
            flines,
            visit_count_lines,
            cross_surgery_hints,
            first_diag_lines,
            drug_change_text,
            presc_end_text,
        )
        gemini_payloads.append({
            "filename": fn,
            "raw_text": rt_part,
            "system_prompt": system_prompt,
            "today_str": today_str,
        })

    sem = asyncio.Semaphore(5)

    async def _guarded_gemini(pd: dict):
        async with sem:
            return await analyze_single_pdf(pd, product_type, reference_date, api_key)

    # 의학 판단 + 메인 Gemini 병렬 실행
    _all_api_results = await asyncio.gather(
        _call_medical_judgment(_mj_type1, _mj_type2, api_key),
        *[_guarded_gemini(pd) for pd in gemini_payloads],
        return_exceptions=True,
    )
    _med_result_raw = _all_api_results[0]
    gemini_out      = list(_all_api_results[1:])

    _med_result: dict = (
        _med_result_raw
        if isinstance(_med_result_raw, dict)
        else {"additional_tests": {}, "treatment_ongoing": {}}
    )
    if "_error" in _med_result:
        retry_warnings.append(f"⚠️ 의학 판단 API 오류 (비치명적): {_med_result['_error']}")

    ai_successes: list[dict] = []
    for i, go in enumerate(gemini_out):
        fn = gemini_payloads[i]["filename"]
        if isinstance(go, BaseException):
            retry_warnings.append(f"⚠️ {fn}: Gemini 병렬 태스크 예외 — {str(go)[:120]}")
            continue
        retry_warnings.extend(go.get("retry_warnings") or [])
        if go.get("error"):
            retry_warnings.append(f"⚠️ {fn}: {go['error']}")
        if go.get("ai_result"):
            ai_successes.append(go["ai_result"])

    if not ai_successes:
        raise AnalysisError("모든 PDF에 대한 AI 분석에 실패했습니다.")

    ai_result = _merge_ai_results(ai_successes)

    # 의학 판단 결과 → disease_stats에 반영
    _at_results = _med_result.get("additional_tests", {})
    _to_results = _med_result.get("treatment_ongoing", {})
    for _jck, _js in disease_stats.items():
        _jdc = (_js.get("diag_code") or _jck).strip()
        if _jdc in _at_results:
            _js["_additional_test_result"] = _at_results[_jdc]
        if _jdc in _to_results:
            _js["_treatment_ongoing_result"] = _to_results[_jdc]

    # 프롬프트/API 관련 대형 문자열 해제
    del system_prompt
    del cross_day_index, seen_code_dates
    gc.collect()

    # ── 결과 병합 ─────────────────────────────────────────────────
    summary_reports = defaultdict(list)
    flagged_codes   = set()
    merged_items    = {}
    code_claimed    = set()

    for item in (code_based_items + ai_result.get("flagged_items", [])):
        # ★ 비-질병 항목 차단 (이중 안전망 — filters.py 가드 외에 AI 결과까지 검사)
        _it_code = (item.get("code") or "").strip().upper()
        _it_name = (item.get("disease") or "").strip()
        if not _KCD_MERGE_RE.match(_it_code):
            continue
        if _it_name and any(pat in _it_name for pat in _NON_DISEASE_NAME_PATTERNS_MERGE):
            continue
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
                if q not in ("Q1", "Q2", "Q3", "Q4"):
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
                q_since_map = {"Q1": _d3m_dt, "Q2": _d1y_dt, "Q3": _d10y_dt, "Q4": _d5y_dt}
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
        _q_since = {"Q1": _d3m_dt, "Q2": _d1y_dt, "Q3": _d10y_dt, "Q4": _d5y_dt}

    for merge_key, m in merged_items.items():
        code_key = m["code"]
        q        = m["duty_question"]
        flagged_codes.add(code_key)

        if product_type == "건강체/표준체 (일반심사)":
            q_map = {
                "Q1": "[1번질문] 3개월 이내 진단·입원·수술·투약",
                "Q2": "[2번질문] 1년 이내 추가검사(재검사)",
                "Q3": "[3번질문] 10년 이내 입원/수술/7회이상통원/30일이상투약",
                "Q4": "[4번질문] 5년 이내 중대질병",
            }
        else:
            q_map = {
                "Q1": "[간편1번질문] 3개월 이내 진단·약 변경",
                "Q2": "[간편2번질문] 10년 이내 입원/수술",
                "Q3": "[간편3번질문] 5년 이내 중대질병",
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

        _chojin  = _ds["chojin_count"]  if _ds else 0
        _jaejin  = _ds["jaejin_count"]  if _ds else 0
        _procedures      = list(_ds.get("procedures", set()) or []) if _ds else []
        _proc_dates      = sorted(_ds.get("procedure_dates", set()) or []) if _ds else []
        _surg_susp       = list(_ds.get("surgery_suspected_names", set()) or []) if _ds else []
        _surg_susp_dates = sorted(_ds.get("surgery_suspected_dates", set()) or []) if _ds else []

        # 의학 판단 결과 반영
        _at_res = _ds.get("_additional_test_result") if _ds else None
        _to_res = _ds.get("_treatment_ongoing_result") if _ds else None

        # additional_tests: AI가 '재검사'로 확정한 경우만 포함, 아니면 raw test names
        if _at_res is not None:
            _add_test_hit    = bool(_at_res.get("is_additional_test"))
            _add_test_reason = _at_res.get("reason", "")
            _additional_tests = [_at_res.get("test_type", "재검사")] if _add_test_hit else []
        else:
            _add_test_hit    = False
            _add_test_reason = ""
            _additional_tests = [t[:50] for t in list(_ds.get("tests_found", set()) or [])[:8]] if _ds else []

        # treatment_ongoing: None이면 미판단
        if _to_res is not None:
            _tx_ongoing        = bool(_to_res.get("is_ongoing"))
            _tx_ongoing_reason = _to_res.get("reason", "")
        else:
            _tx_ongoing        = None
            _tx_ongoing_reason = ""

        summary_reports[q_title].append({
            "first_date":              first_date,
            "latest_date":             latest_date,
            "first_diagnosis_date":    first_diagnosis_date,
            "code":                    m["code"],
            "name":                    m["name"],
            "visit":                   ds_visit_count,
            "chojin_count":            _chojin,
            "jaejin_count":            _jaejin,
            "total_clinic_visit":      _chojin + _jaejin if (_chojin + _jaejin) > 0 else ds_visit_count,
            "med_days":                ds_med_days,
            "med_days_30plus":         ds_med_days >= 30,
            "inpatient":               ds_inpatient_days,
            "inpatient_count":         ds_inpatient_count,
            "inpatient_dates":         _ds_inp_dates if _ds and _ds_inp_dates else [],
            "surgeries":               {m["surgery_name"]} if m["is_surgery"] and m["surgery_name"] else ({"수술"} if m["is_surgery"] else set()),
            "surgery_dates":           sorted(set(m["surgery_dates"])),
            "surgery_count":           len(set(m["surgery_dates"])) if m["is_surgery"] else 0,
            "procedures":              _procedures,
            "procedure_dates":         _proc_dates,
            "surgery_suspected":       _surg_susp,
            "surgery_suspected_dates": _surg_susp_dates,
            "additional_tests":        _additional_tests,
            "additional_test_hit":     _add_test_hit,
            "additional_test_reason":  _add_test_reason,
            "treatment_ongoing":       _tx_ongoing,
            "treatment_ongoing_reason": _tx_ongoing_reason,
            "drug_change_in_3m":       _ds.get("drug_change_in_3m", False) if _ds else False,
            "hospitals":               m["hospitals"],
            "detail":                  m["reason"],
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
