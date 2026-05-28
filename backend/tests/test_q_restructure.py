"""SURIT-009: 신구조 Q1~Q4 함수 + _split_buckets 회귀 테스트.

뇌졸중 I60-I64 포함 / I67 제외, 6대질환 / 10대질환 코드 매칭,
3개월/1년/5년/10년 경계, 처방변경 감지를 검증한다.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from filters import (
    PRODUCT_HEALTH,
    PRODUCT_EASY,
    _split_buckets,
    _build_q1_items,
    _build_q2_health_items,
    _build_q2_easy_items,
    _build_q3_health_items,
    _build_q3_easy_items,
    _build_q4_health_items,
    build_code_based_items,
    EASY_Q3_6CODES,
    HEALTH_Q4_10CODES,
)


def _disease(*, code="K21", name="역류성식도염", first="", latest="",
             visits=(), inpatients=(), surgeries=(), pharma_dates=None,
             drug_change_in_3m=False):
    return {
        "visit_dates": set(visits),
        "inpatient_dates": set(inpatients),
        "surgery_dates": set(surgeries),
        "surgeries": {"수술"} if surgeries else set(),
        "med_dates_basic": {},
        "med_dates_pharma": dict(pharma_dates or {}),
        "drug_names_in_90": set(),
        "drug_names_before_90": set(),
        "_daily_facts": {},
        "_inpatient_days_map": {d: 1 for d in (inpatients or [])},
        "hospitals": {"서울내과"},
        "tests_found": set(),
        "test_events": [],
        "procedures": set(),
        "procedure_dates": set(),
        "surgery_suspected_names": set(),
        "surgery_suspected_dates": set(),
        "chojin_count": 0,
        "jaejin_count": 0,
        "drug_change_in_3m": drug_change_in_3m,
        "first_date": first or "2099-12-31",
        "latest_date": latest or "2000-01-01",
        "diag_code": code,
        "name": name,
        "has_pharma": bool(pharma_dates),
    }


REF = datetime(2026, 5, 12)


# ── _split_buckets ───────────────────────────────────────────────


def test_split_buckets_segregates_by_date_window():
    """3개월/1년/5년/10년 4 시간창 + 입원/수술 별도 버킷으로 분리."""
    ds = {
        "K21": _disease(code="K21", visits=["2026-04-15"], first="2026-04-15"),   # 3개월 + 1년 + 5년
        "K22": _disease(code="K22", visits=["2025-08-15"], first="2025-08-15"),   # 1년 + 5년 (3개월 X)
        "K23": _disease(code="K23", visits=["2023-05-15"], first="2023-05-15"),   # 5년만
        "K24": _disease(code="K24", visits=["2020-05-15"], first="2020-05-15"),   # 10년만 (5년 X)
        "I63": _disease(code="I63", inpatients=["2020-06-15"], first="2020-06-15"),  # 10년 입원
        "M17": _disease(code="M17", surgeries=["2020-07-15"], first="2020-07-15"),   # 10년 수술
    }
    buckets = _split_buckets(ds, REF)
    assert "K21" in buckets["bucket_3m"]
    assert "K22" not in buckets["bucket_3m"]
    assert "K22" in buckets["bucket_1y"]
    assert "K23" not in buckets["bucket_1y"]
    assert "K23" in buckets["bucket_5y_major"]
    assert "K24" not in buckets["bucket_5y_major"]
    assert "I63" in buckets["bucket_10y_hosp"]
    assert "I63" not in buckets["bucket_10y_surg"]
    assert "M17" in buckets["bucket_10y_surg"]


# ── _build_q1_items ───────────────────────────────────────────────


def test_q1_includes_3m_diag():
    """Q1 — 3개월 이내 확정진단 매칭."""
    ds = {"K21": _disease(code="K21", visits=["2026-04-15"], first="2026-04-15")}
    items = _build_q1_items(ds, REF, drug_change_groups=None)
    assert any(it["_rule_id"] == "R-Q1-DIAG-3M" for it in items)


def test_q1_excludes_3m_boundary_past():
    """Q1 — 3개월 이전 진단은 제외."""
    ds = {"K21": _disease(code="K21", visits=["2025-01-15"], first="2025-01-15")}
    items = _build_q1_items(ds, REF, drug_change_groups=None)
    assert not items


def test_q1_drug_change_detected():
    """Q1 — 처방변경 감지."""
    ds = {"E11": _disease(code="E11", first="2023-01-01", latest="2026-04-15",
                          drug_change_in_3m=True)}
    items = _build_q1_items(ds, REF, drug_change_groups={"E11"})
    assert any(it["_rule_id"] == "R-Q1-DRUG-CHANGE" for it in items)


def test_q1_includes_inpatient_and_surgery():
    """Q1 — 3개월 이내 입원·수술 분리 매칭."""
    ds = {
        "K35": _disease(code="K35", inpatients=["2026-04-01"], first="2026-04-01"),
        "K80": _disease(code="K80", surgeries=["2026-04-10"], first="2026-04-10"),
    }
    items = _build_q1_items(ds, REF, drug_change_groups=None)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-Q1-INP-3M" in rule_ids
    assert "R-Q1-SURG-3M" in rule_ids


# ── _build_q2_health_items ────────────────────────────────────────


def test_q2_health_1y_diag_boundary():
    """Q2 건강체 — 1년 이내 확정진단(first_date)만 매칭."""
    ds = {
        "K21": _disease(code="K21", visits=["2025-08-15"], first="2025-08-15"),  # 1년 내
        "K22": _disease(code="K22", visits=["2025-04-15"], first="2025-04-15"),  # 1년 직전 (5/12 기준)
        "K23": _disease(code="K23", visits=["2024-01-15"], first="2024-01-15"),  # 1년 전
    }
    items = _build_q2_health_items(ds, REF)
    codes = {it["code"] for it in items}
    assert "K21" in codes
    # K22 first_date 2025-04-15 가 REF=2026-05-12 의 365일 이전이라 미해당.
    assert "K23" not in codes


def test_q2_health_rule_id_includes_gemini_hint():
    """Q2 건강체 항목 evidence 에 needs_gemini_finding=True 표식."""
    ds = {"K21": _disease(code="K21", visits=["2026-01-15"], first="2026-01-15")}
    items = _build_q2_health_items(ds, REF)
    assert any(it["_rule_id"] == "R-H-Q2-DIAG-1Y" for it in items)
    assert items[0]["_evidence"].get("needs_gemini_finding") is True


# ── _build_q2_easy_items ──────────────────────────────────────────


def test_q2_easy_10y_inpatient_and_surgery():
    """Q2 간편 — 10년 이내 입원/수술 분리 rule_id."""
    ds = {
        "I63": _disease(code="I63", inpatients=["2020-06-15"], first="2020-06-15"),
        "M17": _disease(code="M17", surgeries=["2020-07-15"], first="2020-07-15"),
    }
    items = _build_q2_easy_items(ds, REF)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-E-Q2-INP-10Y" in rule_ids
    assert "R-E-Q2-SURG-10Y" in rule_ids


# ── _build_q3_easy_items (6대질환) ─────────────────────────────────


def test_q3_easy_matches_6codes():
    """Q3 간편 — 6대질환 KCD 매칭."""
    for code in ["C50", "I60", "I63", "I20", "I21", "I34", "K74"]:
        ds = {code: _disease(code=code, visits=["2024-01-01"], first="2024-01-01")}
        items = _build_q3_easy_items(ds, REF)
        assert any(it["_rule_id"] == "R-E-Q3-MAJOR-5Y" for it in items), f"6대 미매칭: {code}"


def test_q3_easy_excludes_i67():
    """Q3 간편 — I67(뇌경색 미동반 뇌졸중)은 6대질환에서 제외."""
    ds = {"I67": _disease(code="I67", visits=["2024-01-01"], first="2024-01-01")}
    items = _build_q3_easy_items(ds, REF)
    assert not items, "I67 은 6대질환에서 제외돼야 함"


def test_q3_easy_excludes_hypertension_and_diabetes():
    """Q3 간편 — 고혈압·당뇨는 6대 아님 (10대만 포함)."""
    for code in ["I10", "E11"]:
        ds = {code: _disease(code=code, visits=["2024-01-01"], first="2024-01-01")}
        items = _build_q3_easy_items(ds, REF)
        assert not items, f"{code} 는 6대질환에서 제외돼야 함"


# ── _build_q4_health_items (10대질환) ─────────────────────────────


def test_q4_health_matches_10codes():
    """Q4 건강체 — 10대질환 KCD 매칭 (6대 + 백혈병/고혈압/당뇨/에이즈)."""
    for code in ["C50", "I60", "I20", "I21", "I34", "K74", "C91", "I10", "E11", "B20"]:
        ds = {code: _disease(code=code, visits=["2024-01-01"], first="2024-01-01")}
        items = _build_q4_health_items(ds, REF)
        assert any(it["_rule_id"] == "R-H-Q4-MAJOR-5Y" for it in items), f"10대 미매칭: {code}"


def test_q4_health_excludes_i67_and_non_listed():
    """Q4 건강체 — I67 / K21 같은 일반 코드는 10대질환 아님."""
    for code in ["I67", "K21", "M54"]:
        ds = {code: _disease(code=code, visits=["2024-01-01"], first="2024-01-01")}
        items = _build_q4_health_items(ds, REF)
        assert not items, f"{code} 는 10대질환에서 제외돼야 함"


# ── 6대/10대 코드 풀 정합성 ────────────────────────────────────────


def test_easy_q3_6codes_contains_only_specified_strokes():
    """EASY_Q3_6CODES 에 I60-I64 만 포함, I65/I66/I67/I68/I69 는 미포함."""
    for c in ["I60", "I61", "I62", "I63", "I64"]:
        assert c in EASY_Q3_6CODES, f"6대 누락: {c}"
    for c in ["I65", "I66", "I67", "I68", "I69"]:
        assert c not in EASY_Q3_6CODES, f"6대에 잘못 포함: {c}"


def test_health_q4_10codes_extends_6codes():
    """HEALTH_Q4_10CODES 는 6대 + 백혈병·고혈압·당뇨·에이즈를 모두 포함."""
    for c in EASY_Q3_6CODES:
        assert c in HEALTH_Q4_10CODES
    for c in ["C91", "I10", "E11", "B20", "B24"]:
        assert c in HEALTH_Q4_10CODES, f"10대 누락: {c}"


# ── build_code_based_items 통합 ──────────────────────────────────


def test_build_code_based_items_health_includes_q1_q2_q3_q4():
    """PRODUCT_HEALTH → Q1+Q2_health+Q3_health+Q4_health 항목 모두 포함."""
    ds = {
        "K21": _disease(code="K21", visits=["2026-04-15"], first="2026-04-15"),       # Q1
        "K22": _disease(code="K22", visits=["2025-08-15"], first="2025-08-15"),       # Q2_health
        # Q3_health: 10년 입원, Q4(10대): 5년 이내 진료 필요
        "I63": _disease(code="I63", inpatients=["2024-06-15"], visits=["2024-06-15"], first="2024-06-15"),
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    qs = {it["duty_question"] for it in items}
    assert "Q1" in qs
    assert "Q2" in qs
    assert "Q3" in qs
    assert "Q4" in qs


def test_build_code_based_items_easy_includes_q1_q2_q3():
    """PRODUCT_EASY → Q1+Q2_easy+Q3_easy 만, Q4 없음."""
    ds = {
        "K21": _disease(code="K21", visits=["2026-04-15"], first="2026-04-15"),       # Q1
        "I63": _disease(code="I63", inpatients=["2020-06-15"], first="2020-06-15"),   # Q2_easy
        "C50": _disease(code="C50", visits=["2024-01-01"], first="2024-01-01"),       # Q3_easy
    }
    items = build_code_based_items(ds, REF, PRODUCT_EASY)
    qs = {it["duty_question"] for it in items}
    assert "Q1" in qs
    assert "Q2" in qs
    assert "Q3" in qs
    assert "Q4" not in qs
