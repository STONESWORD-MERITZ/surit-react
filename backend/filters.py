"""
SURIT 알릴의무 필터링 룰 엔진 (건강체 전용 — SURIT-BUG-008 에서 간편 제거)
- 입력: disease_stats (Dict[group_key, disease_stats_record]), reference_date (datetime), product_type (str)
- 출력: code_based_items: list[dict]

룰은 룰 ID로 추적 가능 (_rule_id):
  R-H-Q1-* : 건강체 Q1 (3개월 진단/입원/수술/투약/상시복용약)
  R-H-Q3-* : 건강체 Q3 (10년 입원/수술/통원7/투약30)
  R-H-Q4-* : 건강체 Q4 (5년 중대질병)

  Q2(건강체 — 1년 추가검사)는 AI 의학 판단(Gemini)에서 결정 → 본 모듈에서는 미생성
"""
from __future__ import annotations

import json
import os
import re as _re
from datetime import datetime, timedelta
from typing import Any, Iterable

# SURIT-005: 날짜 창 로직 중앙화 — _dts_in_range 는 helpers.py 정본을 import
from pipeline.helpers import _dts_in_range

# ── keywords.json 로딩 ────────────────────────────────
_KW_PATH = os.path.join(os.path.dirname(__file__), "keywords.json")

def _load_kw():
    with open(_KW_PATH, encoding="utf-8") as f:
        return json.load(f)

_KW = _load_kw()
HEALTH_Q5_CODES            = tuple(_KW["health_q5_codes"])
# 건강검진·선별검사·예방접종 등 비질병 KCD 코드 (질병으로 집계하지 않음)
NON_DISEASE_CODE_PREFIXES  = tuple(_KW.get("non_disease_code_prefixes", []))


# ── 공유 헬퍼 (helpers.py 와 동일 로직의 인라인 동본) ──
# SURIT-005: _dts_in_range 는 helpers.py 정본 import 로 중앙화함(상단 import 참조).
#            아래 헬퍼들은 인라인 동본으로 유지한다.

def _code_in(code, prefixes) -> bool:
    if code is None:
        return False
    c = str(code).strip()
    if not c:
        return False
    c = c.upper()
    return any(c.startswith(p) for p in prefixes)


def _subtract_years(d, years: int):
    """기준일에서 정확히 N 달력연도 전 날짜 (SURIT-004 — 윤년 보정).

    helpers._subtract_years 와 동일 로직. filters.py 의 순환 임포트 회피
    정책에 따라 인라인한다. 2/29 → 비윤년이면 2/28 로 보정.
    """
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, month=2, day=28)


def _visit_count_in_range(stat: dict[str, Any], since_dt) -> int:
    events = stat.get("visit_events") or []
    if events:
        return len(_dts_in_range(events, since_dt))
    return len(_dts_in_range(stat.get("visit_dates", set()), since_dt))


def _parse_ymd(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        return None


def _max_presc(med_dict, since_dt) -> int:
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
    # 같은 질병 여러 처방은 합산이 아닌 최대값 (helpers._max_presc 와 동일 의미)
    return max(values) if values else 0


# KCD-7 상병코드 패턴: 영문 1자(A~Z) + 숫자 2~4자 + 옵션 숫자/문자
_KCD_RE = _re.compile(r"^[A-Z]\d{2,4}[A-Z0-9]?$")

# 진료비/행위명 키워드 — disease name에 포함되면 비-질병으로 간주
_NON_DISEASE_NAME_PATTERNS = (
    "진찰료", "재진", "초진",
    "조제료", "약국관리료", "약제비", "복약지도료",
    "응급및회송료", "응급의료관리료", "외래환자의약품관리료",
    "주사료", "주사기료", "피하또는근육내주사", "정맥내주사",
    "검사료", "방사선료", "마취료", "이학요법료", "물리치료료",
    "처치및수술", "처치 및수술", "처치및 수 술",
    "치근활택술", "스케일링",
    "재료대", "행위료", "기본진료료", "선택진료료",
    "방문당", "촉탁",
)


def _is_valid_disease(diag_code: str, name: str) -> bool:
    """KCD 상병코드가 있어야 질병으로 인정. 진료비/행위명 항목은 제외."""
    if not diag_code or diag_code in ("$", "해당없음"):
        return False
    if not _KCD_RE.match(diag_code):
        return False
    if any(diag_code.strip().upper().startswith(p) for p in NON_DISEASE_CODE_PREFIXES):
        return False  # 건강검진·선별검사·예방접종 코드는 질병 아님
    if name:
        for pat in _NON_DISEASE_NAME_PATTERNS:
            if pat in name:
                return False
    return True


# ── 상수 ───────────────────────────────────────────────
PRODUCT_HEALTH = "건강체/표준체 (일반심사)"

# 건강체 Q1 ⑤ — 상시복용 약물 카테고리 (성분명 일부 매칭, 대소문자 무시)
CHRONIC_DRUG_CATEGORIES: dict[str, list[str]] = {
    "마약":       ["옥시코돈", "트라마돌", "코데인", "모르핀", "펜타닐", "메타돈"],
    "혈압강하제": ["암로디핀", "로사르탄", "발사르탄", "텔미사르탄", "올메사르탄",
                  "에날라프릴", "리시노프릴", "아테놀롤", "비소프롤롤", "메토프롤롤",
                  "히드로클로로티아지드", "인다파미드"],
    "신경안정제": ["디아제팜", "알프라졸람", "로라제팜", "클로나제팜", "에티졸람", "부스피론"],
    "수면제":     ["졸피뎀", "트리아졸람", "라멜테온", "에스조피클론", "조피클론", "독시라민"],
    "각성제":     ["메틸페니데이트", "암페타민", "모다피닐"],
    "흥분제":     ["카페인"],
    "진통제":     [
        "옥시코돈", "트라마돌", "코데인", "펜타닐",
        "디클로페낙", "나프록센", "셀레콕시브", "에토리콕시브",
        "록소프로펜", "이부프로펜",
    ],
}

# Q1 약물 상시복용 판정 임계 (30일 이상 단일 카테고리 지속 처방)
Q1_CHRONIC_DRUG_DAYS_THRESHOLD = 30

# 가중치
_WEIGHT_CRITICAL_PREFIXES = ("C", "I60", "I61", "I62", "I63", "I64", "I21", "I22", "K74")
_WEIGHT_HIGH_PREFIXES     = ("I10", "I11", "I12", "I13", "I14", "I15",
                             "E10", "E11", "E12", "E13", "E14", "I20")


# ── 헬퍼 ───────────────────────────────────────────────

def _weight_for(code: str) -> str:
    if _code_in(code, _WEIGHT_CRITICAL_PREFIXES): return "critical"
    if _code_in(code, _WEIGHT_HIGH_PREFIXES):     return "high"
    return "mid"


def _sorted_strings(values: Iterable[Any]) -> list[str]:
    return sorted(str(v) for v in (values or []) if v)


def _make_item(
    *, q: str, code: str, disease: str, hospital: str,
    reason: str, date: str = "", weight: str = "mid",
    is_inpatient: bool = False, inpatient_days: int = 0, inpatient_count: int = 0,
    visit_count: int = 0, is_surgery: bool = False, surgery_name: str | None = None,
    med_days: int = 0, first_diagnosis_date: str = "",
    rule_id: str = "", evidence: dict | None = None,
) -> dict:
    return {
        "date": date, "code": code, "disease": disease, "hospital": hospital,
        "duty_question": q, "reason": reason,
        "is_inpatient": is_inpatient, "inpatient_days": inpatient_days,
        "inpatient_count": inpatient_count, "visit_count": visit_count,
        "first_diagnosis_date": first_diagnosis_date,
        "is_surgery": is_surgery, "surgery_name": surgery_name,
        "med_days": med_days, "weight": weight, "_source": "code",
        "_rule_id": rule_id, "_evidence": evidence or {},
    }


def _chronic_drug_hits(drug_names: Iterable[str]) -> dict[str, list[str]]:
    """상시복용 약물 카테고리 매칭 → {카테고리: [매칭된 약품명...]}"""
    hits: dict[str, list[str]] = {}
    for raw in _sorted_strings(drug_names):
        if not raw:
            continue
        s = raw.lower()
        for cat, ingredients in CHRONIC_DRUG_CATEGORIES.items():
            for ing in ingredients:
                if ing.lower() in s:
                    hits.setdefault(cat, []).append(raw)
                    break
    return hits


# ── 공통 날짜 계산 ─────────────────────────────────────

def _cutoffs(reference_date: datetime) -> tuple[datetime, datetime, datetime, datetime]:
    """(d3m, d1y, d5y, d10y) 반환.

    SURIT-004: 5년/10년 창은 윤년 보정을 위해 달력 연도 기준으로 계산한다.
    기존 고정 일수 방식은 윤년 무시로 2~3일 짧았음.
    3개월/1년 창은 윤년 영향이 없어 고정 일수를 유지한다.
    """
    return (
        reference_date - timedelta(days=90),
        reference_date - timedelta(days=365),
        _subtract_years(reference_date, 5),    # SURIT-004: 달력 기준 5년
        _subtract_years(reference_date, 10),   # SURIT-004: 달력 기준 10년
    )


# ── 메인 진입점 ────────────────────────────────────────

def build_code_based_items(
    disease_stats: dict[str, dict[str, Any]],
    reference_date: datetime,
    product_type: str,
    *,
    drug_change_groups: set[str] | None = None,
) -> list[dict]:
    """
    필터 룰 적용해 code_based_items 리스트 반환.

    Args:
        disease_stats: analyzer.run_analysis 가 빌드한 질병별 통합 통계.
        reference_date: 청약일/기준일 (datetime).
        product_type: PRODUCT_HEALTH (SURIT-BUG-008 이후 건강체만 지원).
        drug_change_groups: 3개월 내 약 변경 감지된 group_key 집합.
                            None 이면 disease_stats[g].get("drug_change_in_3m") 사용.
    """
    # SURIT-BUG-008: 간편심사 분기 제거. PRODUCT_HEALTH 또는 미지정 모두
    # 건강체 룰로 처리한다. drug_change_groups 는 _build_health 가 직접
    # disease_stats[g]["drug_change_in_3m"] 를 참조하므로 본 함수에서는 사용 안 함.
    _ = drug_change_groups  # 시그니처 호환 유지
    if product_type and product_type != PRODUCT_HEALTH:
        # 알 수 없는 product_type 도 건강체로 fallback (UI/main.py 가
        # 표준 외 값을 보낼 가능성 차단).
        pass
    return _build_health(disease_stats, reference_date)


# ── 건강체 룰 ──────────────────────────────────────────

def _build_health(
    disease_stats: dict[str, dict[str, Any]],
    reference_date: datetime,
) -> list[dict]:
    items: list[dict] = []
    d3m, d1y, d5y, d10y = _cutoffs(reference_date)

    for gk, s in disease_stats.items():
        dc = (s.get("diag_code") or "").strip().upper()
        nm = (s.get("name") or "").strip()
        if not _is_valid_disease(dc, nm):
            continue
        if not nm:
            nm = dc
        hp = " / ".join(_sorted_strings(s.get("hospitals", set()))[:2]) or "정보 없음"
        fd = s.get("first_date", "2099-12-31")
        ld = s.get("latest_date", "2000-01-01")

        # ── 기간 필터링 ──
        inp_3m   = _dts_in_range(s.get("inpatient_dates", set()), d3m)
        surg_3m  = _dts_in_range(s.get("surgery_dates", set()), d3m)
        inp_10y  = _dts_in_range(s.get("inpatient_dates", set()), d10y)
        surg_10y = _dts_in_range(s.get("surgery_dates", set()), d10y)
        visit_3m  = _dts_in_range(s.get("visit_dates", set()), d3m)
        visit_3m_count = _visit_count_in_range(s, d3m)
        visit_10y = _dts_in_range(s.get("visit_dates", set()), d10y)
        visit_10y_count = _visit_count_in_range(s, d10y)
        all_5y   = _dts_in_range(
            s.get("visit_dates", set()) | s.get("inpatient_dates", set()) | s.get("surgery_dates", set()),
            d5y,
        )

        # ── 입원일수/횟수 ──
        inp_map   = s.get("_inpatient_days_map", {})
        inp3m_days  = sum(inp_map.get(d, 1) for d in inp_3m)  if inp_3m  else 0
        inp10y_days = sum(inp_map.get(d, 1) for d in inp_10y) if inp_10y else 0

        # ── 투약일수 ──
        med_pharma = s.get("med_dates_pharma_episode") or s.get("med_dates_pharma", {})
        presc_3m   = _max_presc(med_pharma, d3m)
        presc_10y  = _max_presc(med_pharma, d10y)
        presc_5y   = _max_presc(med_pharma, d5y)

        wt = _weight_for(dc)
        sn = next(iter(_sorted_strings(s.get("surgeries", set()))), None)

        ci = lambda **kw: _make_item(code=dc, disease=nm, hospital=hp,
                                     first_diagnosis_date=fd, **kw)

        # ── Q1 룰 ──

        # R-H-Q1-DIAG-3M: 3개월 이내 진단 기록 (입원/수술 없을 때)
        fd_dt = _parse_ymd(fd)
        if (fd_dt and fd_dt >= d3m
                and not inp_3m and not surg_3m
                and (visit_3m or fd_dt <= reference_date)):
            items.append(ci(
                q="Q1", rule_id="R-H-Q1-DIAG-3M",
                reason=f"3개월 이내 진단 기록: {nm} ({dc})",
                date=fd, weight=wt,
                visit_count=visit_3m_count, med_days=presc_3m,
                evidence={"first_date": fd, "code": dc},
            ))

        # R-H-Q1-INP-3M: 3개월 이내 입원
        if inp_3m:
            items.append(ci(
                q="Q1", rule_id="R-H-Q1-INP-3M",
                reason=f"3개월 이내 입원 ({inp3m_days}일) — 기본진료 확인",
                date=max(inp_3m), weight=wt,
                is_inpatient=True, inpatient_days=inp3m_days,
                inpatient_count=len(inp_3m),
                visit_count=visit_3m_count, med_days=presc_3m,
                evidence={"dates": inp_3m, "actual_days": inp3m_days},
            ))

        # R-H-Q1-SURG-3M: 3개월 이내 수술
        if surg_3m:
            items.append(ci(
                q="Q1", rule_id="R-H-Q1-SURG-3M",
                reason=f"3개월 이내 수술: {sn or '수술'} — 세부진료 확인",
                date=max(surg_3m), weight=wt,
                is_surgery=True, surgery_name=sn,
                visit_count=visit_3m_count, med_days=presc_3m,
                evidence={"dates": surg_3m, "surgery": sn},
            ))

        # R-H-Q1-CHRONIC-DRUG: 상시복용약 (혈압강하제/수면제 등) 30일 이상
        chronic_hits = _chronic_drug_hits(s.get("drug_names_in_90", set()))
        chronic_fired = False
        if chronic_hits and presc_3m >= Q1_CHRONIC_DRUG_DAYS_THRESHOLD:
            cat = next((c for c in CHRONIC_DRUG_CATEGORIES if c in chronic_hits), next(iter(chronic_hits)))
            drugs = chronic_hits[cat]
            items.append(ci(
                q="Q1", rule_id="R-H-Q1-CHRONIC-DRUG",
                reason=f"3개월 이내 상시복용약: {cat} ({', '.join(drugs[:2])})",
                date=ld, weight="high",
                med_days=presc_3m,
                visit_count=visit_3m_count,
                evidence={"category": cat, "matched_drugs": drugs, "presc_days": presc_3m},
            ))
            chronic_fired = True

        # R-H-Q1-MED-3M: 3개월 이내 처방 투약 (상시복용약 중복 방지)
        if presc_3m > 0 and not chronic_fired:
            items.append(ci(
                q="Q1", rule_id="R-H-Q1-MED-3M",
                reason=f"3개월 이내 처방 투약 ({presc_3m}일)",
                date=ld, weight=wt,
                med_days=presc_3m, visit_count=visit_3m_count,
                evidence={"presc_days": presc_3m, "source": "처방조제"},
            ))

        # ── Q3 룰 (입원·수술 유무와 무관하게 모두 생성) ──

        # R-H-Q3-INP-10Y: 10년 이내 입원
        if inp_10y:
            items.append(ci(
                q="Q3", rule_id="R-H-Q3-INP-10Y",
                reason=f"10년 이내 입원 ({inp10y_days}일) — 기본진료 확인",
                date=max(inp_10y), weight=wt,
                is_inpatient=True, inpatient_days=inp10y_days,
                inpatient_count=len(inp_10y),
                visit_count=visit_10y_count, med_days=presc_10y,
                evidence={"dates": inp_10y, "actual_days": inp10y_days},
            ))

        # R-H-Q3-SURG-10Y: 10년 이내 수술
        if surg_10y:
            items.append(ci(
                q="Q3", rule_id="R-H-Q3-SURG-10Y",
                reason=f"10년 이내 수술: {sn or '수술'} — 세부진료 확인",
                date=max(surg_10y), weight=wt,
                is_surgery=True, surgery_name=sn,
                is_inpatient=bool(inp_10y), inpatient_days=inp10y_days,
                inpatient_count=len(inp_10y),
                visit_count=visit_10y_count, med_days=presc_10y,
                evidence={"dates": surg_10y, "surgery": sn},
            ))

        # R-H-Q3-VISIT-7: 10년 이내 7회 이상 통원 (입원/수술 유무 무관)
        if visit_10y_count >= 7:
            items.append(ci(
                q="Q3", rule_id="R-H-Q3-VISIT-7",
                reason=f"10년 이내 7회 이상 통원 ({visit_10y_count}회) — 기본진료 확인",
                date=ld, weight=wt,
                visit_count=visit_10y_count, med_days=presc_10y,
                evidence={"visit_count": visit_10y_count, "dates": visit_10y},
            ))

        # R-H-Q3-MED-30D: 10년 이내 30일 이상 투약 (입원/수술 유무 무관)
        if presc_10y >= 30:
            items.append(ci(
                q="Q3", rule_id="R-H-Q3-MED-30D",
                reason=f"10년 이내 30일 이상 투약 ({presc_10y}일) — 처방조제 확인",
                date=ld, weight=wt,
                visit_count=visit_10y_count, med_days=presc_10y,
                evidence={"presc_days": presc_10y, "source": "처방조제"},
            ))

        # ── Q4 룰 ──

        # R-H-Q4-CRITICAL-5Y: 5년 이내 중대질병
        if _code_in(dc, HEALTH_Q5_CODES) and all_5y:
            inp_5y  = _dts_in_range(s.get("inpatient_dates", set()), d5y)
            surg_5y = _dts_in_range(s.get("surgery_dates", set()), d5y)
            inp5y_days = sum(inp_map.get(d, 1) for d in inp_5y) if inp_5y else 0
            items.append(ci(
                q="Q4", rule_id="R-H-Q4-CRITICAL-5Y",
                reason=f"5년 이내 중대질병: {nm} ({dc})",
                date=max(all_5y), weight="critical" if wt == "critical" else "high",
                is_inpatient=bool(inp_5y), inpatient_days=inp5y_days,
                inpatient_count=len(inp_5y),
                visit_count=_visit_count_in_range(s, d5y),
                med_days=presc_5y,
                is_surgery=bool(surg_5y), surgery_name=sn if surg_5y else None,
                evidence={"code": dc, "matched_prefix": "HEALTH_Q5_CODES"},
            ))

    return items
