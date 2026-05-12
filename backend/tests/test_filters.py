import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from filters import (
    build_code_based_items,
    PRODUCT_HEALTH,
    PRODUCT_EASY,
    _chronic_drug_hits,
    CHRONIC_DRUG_CATEGORIES,
)


def _disease(
    *,
    code="K21",
    name="역류성식도염",
    first="",
    latest="",
    visits=(),
    inpatients=(),
    surgeries=(),
    pharma_dates=None,
    drugs_in_90=(),
    drugs_before_90=(),
):
    return {
        "visit_dates": set(visits),
        "inpatient_dates": set(inpatients),
        "surgery_dates": set(surgeries),
        "surgeries": {"수술"} if surgeries else set(),
        "med_dates_basic": {},
        "med_dates_pharma": dict(pharma_dates or {}),
        "drug_names_in_90": set(drugs_in_90),
        "drug_names_before_90": set(drugs_before_90),
        "_daily_facts": {},
        "_inpatient_days_map": {d: 1 for d in (inpatients or [])},
        "hospitals": {"서울내과"},
        "tests_found": set(),
        "procedures": set(),
        "procedure_dates": set(),
        "surgery_suspected_names": set(),
        "surgery_suspected_dates": set(),
        "chojin_count": 0,
        "jaejin_count": 0,
        "drug_change_in_3m": False,
        "first_date": first or "2099-12-31",
        "latest_date": latest or "2000-01-01",
        "diag_code": code,
        "name": name,
        "has_pharma": bool(pharma_dates),
    }


REF = datetime(2026, 5, 12)


# ── 건강체 ──────────────────────────────────────────────────────


def test_health_q1_inpatient_3m():
    ds = {
        "K21": _disease(
            code="K21",
            inpatients=["2026-04-01"],
            first="2026-04-01",
            latest="2026-04-05",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    assert any(it["_rule_id"] == "R-H-Q1-INP-3M" for it in items)


def test_health_q1_diag_only():
    """입원/수술 없이 진단만 3개월 내 → Q1 확정진단"""
    ds = {
        "K21": _disease(
            code="K21",
            visits=["2026-04-20"],
            first="2026-04-20",
            latest="2026-04-20",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    diag_items = [it for it in items if it["_rule_id"] == "R-H-Q1-DIAG-3M"]
    assert len(diag_items) == 1


def test_health_q3_visit_and_surgery_coexist():
    """통원 7회 + 수술 → 두 사유 모두 생성 (배타 X)"""
    visits = [f"2025-{m:02d}-15" for m in range(1, 10)]  # 9회
    ds = {
        "K21": _disease(
            code="K21",
            visits=visits,
            surgeries=["2025-06-15"],
            first="2025-01-15",
            latest="2025-09-15",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-H-Q3-VISIT-7" in rule_ids
    assert "R-H-Q3-SURG-10Y" in rule_ids


def test_health_q3_med_30d_with_inpatient():
    """투약 30일 + 입원 → 두 사유 모두"""
    ds = {
        "E11": _disease(
            code="E11",
            inpatients=["2024-05-01"],
            pharma_dates={"2024-05-10": 60},
            first="2024-05-01",
            latest="2024-05-10",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-H-Q3-MED-30D" in rule_ids
    assert "R-H-Q3-INP-10Y" in rule_ids


def test_health_q4_critical_codes():
    """C/D0/I10~I15/I20~I22/I60~I64/K74/E10~E14/B20~B24 모두 Q4 매칭"""
    for code in ["C50", "D00", "I10", "I20", "I21", "I60", "I63", "K74", "E11", "B20"]:
        ds = {
            code: _disease(
                code=code,
                visits=["2024-01-01"],
                first="2024-01-01",
                latest="2024-01-01",
            )
        }
        items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
        assert any(
            it["_rule_id"] == "R-H-Q4-CRITICAL-5Y" for it in items
        ), f"Q4 미매칭: {code}"


def test_health_q1_chronic_drug_hypertension():
    """혈압강하제 30일 이상 → Q1"""
    ds = {
        "I10": _disease(
            code="I10",
            pharma_dates={"2026-04-01": 30},
            drugs_in_90={"암로디핀 5mg"},
            first="2024-01-01",
            latest="2026-04-01",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    chronic = [it for it in items if it["_rule_id"] == "R-H-Q1-CHRONIC-DRUG"]
    assert len(chronic) == 1
    assert chronic[0]["_evidence"]["category"] == "혈압강하제"


def test_health_q1_med_3m_no_chronic():
    """처방 투약 3개월 이내, 상시복용약 미매칭 → R-H-Q1-MED-3M"""
    ds = {
        "K21": _disease(
            code="K21",
            pharma_dates={"2026-04-10": 7},
            first="2025-01-01",
            latest="2026-04-10",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-H-Q1-MED-3M" in rule_ids
    assert "R-H-Q1-CHRONIC-DRUG" not in rule_ids


def test_health_q3_visit7_with_inpatient():
    """입원 있어도 통원 7회 이상이면 Q3-VISIT-7 별도 생성"""
    visits = [f"2023-{m:02d}-10" for m in range(1, 9)]  # 8회
    ds = {
        "M17": _disease(
            code="M17",
            visits=visits,
            inpatients=["2023-06-01"],
            first="2023-01-10",
            latest="2023-08-10",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-H-Q3-VISIT-7" in rule_ids
    assert "R-H-Q3-INP-10Y" in rule_ids


# ── 간편 ────────────────────────────────────────────────────────


def test_easy_q2_inpatient_only_no_visit_rule():
    """간편 Q2는 통원/투약 사유 없어야 한다"""
    visits = [f"2025-{m:02d}-15" for m in range(1, 10)]
    ds = {
        "K21": _disease(
            code="K21",
            visits=visits,
            pharma_dates={"2025-01-01": 60},
            first="2025-01-15",
            latest="2025-09-15",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_EASY)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-E-Q2-INP-10Y" not in rule_ids  # 입원 없음
    assert all(not rid.startswith("R-E-Q2-VISIT") for rid in rule_ids)
    assert all(not rid.startswith("R-E-Q2-MED") for rid in rule_ids)


def test_easy_q1_drug_change():
    ds = {
        "E11": _disease(code="E11", first="2023-01-01", latest="2026-04-01")
    }
    ds["E11"]["drug_change_in_3m"] = True
    items = build_code_based_items(
        ds, REF, PRODUCT_EASY, drug_change_groups={"E11"}
    )
    assert any(it["_rule_id"] == "R-E-Q1-DRUG-CHANGE" for it in items)


def test_easy_q3_only_simple_codes():
    """간편 Q3는 simple_q3_allowed_prefixes 만"""
    ds_diabetes = {
        "E11": _disease(code="E11", visits=["2024-01-01"], first="2024-01-01", latest="2024-01-01")
    }
    ds_cancer = {
        "C50": _disease(code="C50", visits=["2024-01-01"], first="2024-01-01", latest="2024-01-01")
    }
    items_d = build_code_based_items(ds_diabetes, REF, PRODUCT_EASY)
    items_c = build_code_based_items(ds_cancer, REF, PRODUCT_EASY)
    assert not any(
        it["_rule_id"] == "R-E-Q3-CRITICAL-5Y" for it in items_d
    )  # 당뇨 X
    assert any(
        it["_rule_id"] == "R-E-Q3-CRITICAL-5Y" for it in items_c
    )  # 암 O


def test_easy_q1_inpatient_3m():
    ds = {
        "I63": _disease(
            code="I63",
            inpatients=["2026-03-01"],
            first="2026-03-01",
            latest="2026-03-15",
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_EASY)
    assert any(it["_rule_id"] == "R-E-Q1-INP-3M" for it in items)
    assert any(it["_rule_id"] == "R-E-Q3-CRITICAL-5Y" for it in items)  # 뇌경색 Q3도


# ── 약물 카테고리 매처 ───────────────────────────────────────────


def test_chronic_drug_hits_basic():
    hits = _chronic_drug_hits(["암로디핀 5mg", "졸피뎀정 10mg", "타이레놀"])
    assert "혈압강하제" in hits
    assert "수면제" in hits


def test_chronic_drug_hits_empty():
    assert _chronic_drug_hits([]) == {}
    assert _chronic_drug_hits(["비타민C", "오메가3"]) == {}


def test_chronic_drug_hits_multiple_categories():
    hits = _chronic_drug_hits(["암로디핀 5mg", "디아제팜 2mg", "졸피뎀 10mg"])
    assert "혈압강하제" in hits
    assert "신경안정제" in hits
    assert "수면제" in hits
