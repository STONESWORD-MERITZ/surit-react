"""공용 헬퍼 함수 + 상수 + AnalysisError — analyzer.py 에서 이동."""
from __future__ import annotations

import functools
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd

# ── keywords.json 로딩 ────────────────────────────────────────────
_KW_PATH = os.path.join(os.path.dirname(__file__), "..", "keywords.json")


def _load_keywords():
    with open(_KW_PATH, encoding="utf-8") as f:
        return json.load(f)


_KW = _load_keywords()

surg_keywords          = _KW["surg_keywords"]
surg_negative_keywords = _KW["surg_negative_keywords"]
test_keywords          = _KW["test_keywords"]
nhis_surg_keywords     = _KW["nhis_surg_keywords"]
HEALTH_Q5_CODES            = tuple(_KW["health_q5_codes"])
_FTYPE_KW                  = _KW["detect_file_type_keywords"]
SURGERY_COST_KEYWORDS      = _KW["surgery_cost_keywords"]
PROCEDURE_KEYWORDS         = _KW["procedure_keywords"]

SURGERY_COST_THRESHOLD   = 500_000
PROCEDURE_COST_THRESHOLD = 300_000


# ── 예외 클래스 ───────────────────────────────────────────────────
class AnalysisError(Exception):
    def __init__(self, message, raw_response=None):
        super().__init__(message)
        self.raw_response = raw_response


# ── 필드 정규화 ───────────────────────────────────────────────────
def _norm_field_name(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[\s\n\r\t·ㆍ/\\&()\[\]_-]+", "", str(value)).lower()


def get_val(row, possible_keys):
    normalized_targets = [_norm_field_name(pk) for pk in possible_keys]
    normalized_items = [(_norm_field_name(k), k) for k in row.keys()]

    def read_non_empty(raw_key):
        val = row[raw_key]
        if not pd.notna(val):
            return None
        text = str(val).strip()
        return text if text else None

    for target in normalized_targets:
        if not target:
            continue
        for nk, raw_key in normalized_items:
            if nk == target:
                val = read_non_empty(raw_key)
                if val is not None:
                    return val

    for target in normalized_targets:
        if not target:
            continue
        for nk, raw_key in normalized_items:
            if target in nk:
                val = read_non_empty(raw_key)
                if val is not None:
                    return val

    return ""


def _clean_disease_name(name: str | None) -> str:
    if not name:
        return ""
    cleaned = str(name).strip()
    cleaned = re.sub(r"^\((?:양방|한방)\)\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    spacing_repairs = {
        "만 성": "만성", "급 성": "급성", "상 세": "상세", "불 명": "불명",
        "양 쪽": "양쪽", "경 추": "경추", "요 추": "요추", "흉 추": "흉추",
        "발 목": "발목", "무 릎": "무릎", "관절 증": "관절증", "염 좌": "염좌",
        "긴 장": "긴장", "신 체": "신체", "부 위": "부위", "표 재성": "표재성",
        "손 상": "손상", "위 염": "위염", "비 인두": "비인두", "바 이러스": "바이러스",
        "코 로나": "코로나", "치 주염": "치주염", "단순치 주염": "단순치주염",
    }
    for before, after in spacing_repairs.items():
        cleaned = cleaned.replace(before, after)
    cleaned = cleaned.replace("양쪽원발성", "양쪽 원발성")
    cleaned = cleaned.replace("의염좌", "의 염좌")
    cleaned = cleaned.replace("및긴장", "및 긴장")
    cleaned = cleaned.replace("부위 의표재성", "부위의 표재성")
    if cleaned in ("$", "해당없음"):
        return ""
    return cleaned


def get_diagnosis_code(row) -> str:
    raw_code = get_val(row, ["주상병코드", "주상병 코드", "주상병기호", "주상병 기호"])
    if not raw_code:
        raw_code = get_val(row, ["상병코드", "상병 코드", "진단코드", "진단 코드"])
    return raw_code


def get_diagnosis_name(row) -> str:
    return _clean_disease_name(get_val(row, ["주상병명", "주 상병명", "상병명", "상병 명"]))


def normalize_code(raw: str | None) -> str:
    if raw is None:
        return ""
    code = str(raw).strip()
    if not code:
        return ""
    code = code.upper()
    if not code or code == "$":
        return ""
    code = code.replace(".", "").replace("-", "").replace(" ", "")
    if len(code) >= 3 and code[0] in ("A", "B") and code[1].isalpha():
        code = code[1:]
    if len(code) >= 2 and code[0].isalpha() and len(code) > 1:
        alpha = code[0]
        digits = code[1:]
        while digits.startswith("000"):
            digits = digits[1:]
        if len(digits) >= 2:
            code = alpha + digits
    if code and code[0] == "1" and len(code) >= 3:
        candidate = "I" + code[1:]
        if candidate[1:3].isdigit():
            code = candidate
    return code


def format_kcd_code(code: str | None) -> str:
    c = normalize_code(code)
    m = re.match(r"^([A-Z])(\d{2})([A-Z0-9]+)$", c)
    if not m:
        return c
    return f"{m.group(1)}{m.group(2)}.{m.group(3)}"


DISCLOSURE_CODE_GROUPS = {
    "M54": {"code": "M54", "name": "등통증(경추 및 요추)"},
}


def disclosure_group_code(code: str) -> str:
    c = normalize_code(code)
    for prefix, group in DISCLOSURE_CODE_GROUPS.items():
        if c.startswith(prefix):
            return group["code"]
    return c


def disclosure_group_name(code: str, fallback: str = "") -> str:
    c = normalize_code(code)
    for prefix, group in DISCLOSURE_CODE_GROUPS.items():
        if c.startswith(prefix):
            return group["name"]
    return fallback


def _keep_basic_general_row(code: str) -> bool:
    return disclosure_group_code(code) in {"M54"}


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


def _is_surgery_match(text: str) -> bool:
    if not text:
        return False
    has_positive = any(kw in text for kw in surg_keywords)
    if not has_positive:
        return False
    has_negative = any(kw in text for kw in surg_negative_keywords)
    if has_negative:
        strong_surg = ["수술", "절제", "절개", "적출", "봉합", "이식", "절단", "재건", "치환", "관혈", "배농"]
        return any(kw in text for kw in strong_surg)
    return True


def _is_confirmed_surgery_cost_kw(text: str) -> bool:
    if not text:
        return False
    tl = text.lower()
    return any(kw.lower() in tl for kw in SURGERY_COST_KEYWORDS)


def _is_procedure_kw(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in PROCEDURE_KEYWORDS)


_BILLING_CODE_KW = (
    "진찰료", "관리료", "기본료", "지도료",
    "처방조제", "약국관리", "의약품관리", "약품관리",
    "방문당", "1일분", "1회당", "회당", "회분",
    "조제기본", "복약지도", "입원료", "처방료",
    "피하또는", "근육내주사", "정맥내주사",
    "악당", "치석제거", "치근활택",
)


def _is_billing_code(name: str) -> bool:
    if not name:
        return False
    if "[" in name and ("/" in name or "악당" in name):
        return True
    return any(kw in name for kw in _BILLING_CODE_KW)


def _to_int_cost(raw: str) -> int:
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
    if code_str:
        return code_str
    return re.sub(r"[\s\d\.\-_/]", "", name_str or "")[:18]


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
    dose_match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|ml|g|ug|IU)', name, flags=re.IGNORECASE)
    if dose_match:
        raw_dose = float(dose_match.group(1))
        unit = dose_match.group(2).lower()
        dose = raw_dose * _DOSE_UNIT_TO_MG.get(unit, 1.0)
    else:
        dose = 0.0
    base = re.sub(r'\d+(\.\d+)?\s*(mg|mcg|ml|g|ug|IU)', '', name, flags=re.IGNORECASE)
    base = _DRUG_PAREN_RE.sub('', base)
    base = _DRUG_SUFFIX_RE.sub('', base)
    base = _DRUG_MAKER_RE.sub('', base)
    base = re.sub(r'[\s\-_/·]+', '', base).lower().strip()
    return base, dose


@functools.lru_cache(maxsize=256)
def extract_json(text: str) -> dict:
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


def _sorted_strings(values) -> list[str]:
    return sorted(str(v) for v in (values or []) if v)


def _code_in(code, prefixes):
    if code is None:
        return False
    c = str(code).strip()
    if not c:
        return False
    c = c.upper()
    return any(c.startswith(p) for p in prefixes)


def _dts_in_range(date_set, since_dt):
    """날짜 집합에서 since_dt 이후(경계 포함, >=) 날짜만 정렬해 반환 — 날짜 창 멤버십 정본.

    SURIT-005: 분석 전 모듈의 단일 진입점. filters.py 도 이 함수를 import 한다.
    """
    result = []
    for d in date_set:
        try:
            if d and datetime.strptime(d, "%Y-%m-%d") >= since_dt:
                result.append(d)
        except ValueError:
            pass
    return sorted(result)


def _add_days(date_str: str, days: int) -> str:
    dt = _parse_ymd(date_str)
    if not dt or days <= 1:
        return date_str
    return (dt + timedelta(days=days - 1)).strftime("%Y-%m-%d")


def _inpatient_periods_in_range(stat: dict, since_dt) -> list[dict]:
    seen = {}
    for period in stat.get("inpatient_periods") or []:
        if not isinstance(period, dict):
            continue
        start = str(period.get("start") or "")
        if not start:
            continue
        start_dt = _parse_ymd(start)
        if not start_dt or start_dt < since_dt:
            continue
        days = int(period.get("days") or 0)
        end = str(period.get("end") or "") or _add_days(start, days)
        key = (start, end)
        prev = seen.get(key)
        if prev is None or days > int(prev.get("days") or 0):
            seen[key] = {"start": start, "end": end, "days": days}
    return sorted(seen.values(), key=lambda x: (x["start"], x["end"]))


def _inpatient_end_dates_in_range(stat: dict, since_dt) -> set[str]:
    return {p["end"] for p in _inpatient_periods_in_range(stat, since_dt) if p.get("end")}


def _visit_count_in_range(stat, since_dt) -> int:
    events = stat.get("visit_events") or []
    if events:
        return len(_dts_in_range(events, since_dt))
    return len(_dts_in_range(stat.get("visit_dates", set()), since_dt))


def _parse_ymd(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def _subtract_years(d, years: int):
    """기준일에서 정확히 N 달력연도 전 날짜를 반환한다 (SURIT-004).

    고정 일수(예: 5년=1825일, 10년=3650일)는 윤년을 무시해 실제 달력
    5년/10년보다 2~3일 짧다. 보험 고지 기준은 달력 연도(anniversary)이므로
    연(year)만 빼고 같은 월·일을 유지한다. 2/29 기준일이 비윤년에 닿으면
    2/28로 보정한다.
    """
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, month=2, day=28)


def _recent_detail_test_events(stat: dict, since_dt: datetime) -> list[dict]:
    events = []
    daily_facts = stat.get("_daily_facts", {}) or {}
    for event in stat.get("test_events") or []:
        if not isinstance(event, dict):
            continue
        date = str(event.get("date") or "")
        name = str(event.get("name") or "").strip()
        if not date or not name:
            continue
        dt = _parse_ymd(date)
        if not dt or dt < since_dt:
            continue
        day_fact = daily_facts.get(date, {}) or {}
        same_day_actions = _sorted_strings(day_fact.get("detail_proc_names", set()))[:12]
        events.append({
            "date": date,
            "name": name[:80],
            "hospital": str(event.get("hospital") or "")[:40],
            "same_day_detail_actions": [x[:80] for x in same_day_actions],
            "source": "detail",
        })
    return sorted(events, key=lambda x: (x["date"], x["name"], x.get("hospital", "")))


def _detail_test_type_count(events: list[dict]) -> int:
    return len({str(event.get("name") or "").strip() for event in events if event.get("name")})


def _max_presc(med_dict, since_dt):
    if not med_dict:
        return 0
    values = []
    for d, v in med_dict.items():
        if not d or datetime.strptime(d, "%Y-%m-%d") < since_dt:
            continue
        if isinstance(v, dict):
            values.extend(int(x or 0) for x in v.values())
        else:
            values.append(int(v or 0))
    return max(values) if values else 0


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
