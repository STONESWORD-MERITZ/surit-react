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
    test_events=(),
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
        "test_events": list(test_events),
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


def test_health_q3_med_30d_uses_max_episode_not_sum():
    """투약일수는 합산이 아닌 단일 처방 최대값 기준 (합산 버그 방지).

    같은 질병에 짧은 처방을 여러 번 받았다고 '계속 30일 이상 투약'으로
    보지 않는다. 단일 처방이 30일 이상일 때만 Q3 투약으로 본다.
    """
    # ① 한 번에 35일 처방 → Q3 투약 해당
    ds = {
        "M54": _disease(
            code="M54",
            name="등통증(경추 및 요추)",
            visits=["2023-09-04"],
            first="2023-09-04",
            latest="2023-09-04",
        )
    }
    ds["M54"]["med_dates_pharma_episode"] = {
        "2023-09-04": {"민재활의학과의원": 35},
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    med_items = [it for it in items if it["_rule_id"] == "R-H-Q3-MED-30D"]
    assert len(med_items) == 1
    assert med_items[0]["med_days"] >= 30

    # ② 7일 처방을 여러 번(합산 40일이지만 최대 7일) → Q3 투약 미해당
    ds2 = {
        "M54": _disease(
            code="M54",
            name="등통증(경추 및 요추)",
            visits=[f"2023-09-{d:02d}" for d in range(1, 8)],
            first="2023-09-01",
            latest="2023-09-27",
        )
    }
    ds2["M54"]["med_dates_pharma_episode"] = {
        "2023-09-04": {"민재활의학과의원": 7, "하나로약국": 7},
        "2023-09-11": {"민재활의학과의원": 7, "하나로약국": 7},
        "2023-09-27": {"신원비뇨기과의원": 6, "성모약국": 6},
    }
    items2 = build_code_based_items(ds2, REF, PRODUCT_HEALTH)
    assert not [it for it in items2 if it["_rule_id"] == "R-H-Q3-MED-30D"]


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


def test_health_q2_detail_events_are_not_code_based_final_judgment():
    """세부진료 반복검사는 API 판단 후보일 뿐 코드 기반 Q2로 확정하지 않는다."""
    ds = {
        "R51": _disease(
            code="R51",
            name="두통",
            visits=["2026-01-10", "2026-02-10"],
            first="2026-01-10",
            latest="2026-02-10",
            test_events=[
                {"date": "2026-01-10", "name": "혈액검사", "source": "detail"},
                {"date": "2026-02-10", "name": "혈액검사", "source": "detail"},
            ],
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-H-Q2-TEST-REPEAT-SUSPECT" not in rule_ids
    assert "R-H-Q2-TEST-API" not in rule_ids


def test_health_q2_old_repeat_tests_do_not_match():
    """건강체 Q2는 1년 이내 추가검사 기준이므로 오래된 반복검사는 제외."""
    ds = {
        "R51": _disease(
            code="R51",
            name="두통",
            visits=["2024-01-10", "2024-02-10"],
            first="2024-01-10",
            latest="2024-02-10",
            test_events=[
                {"date": "2024-01-10", "name": "혈액검사", "source": "detail"},
                {"date": "2024-02-10", "name": "영상검사", "source": "detail"},
            ],
        )
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    rule_ids = {it["_rule_id"] for it in items}
    assert "R-H-Q2-TEST-REPEAT-SUSPECT" not in rule_ids


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


def test_filter_rejects_non_kcd_name():
    """진료비/행위명 entry는 KCD 패턴 불일치 시 차단되어야 함"""
    ds = {
        # 유효 disease — Q3 통원 7회 이상으로 flagging
        "K05": _disease(
            code="K05",
            name="치주염",
            visits=[f"2025-{m:02d}-15" for m in range(1, 10)],
            first="2025-01-15",
            latest="2025-09-15",
        ),
        # 비-disease entry (KCD 코드 없음 → filters가 차단해야 함)
        "재진진찰료|치과의|2025-10": {
            **_disease(name="재진진찰료"),
            "diag_code": "",
        },
        # PHARMA 임시 key (KCD 코드 없음 → filters가 차단해야 함)
        "PHARMA|암로디핀|2025-10": {
            **_disease(name="암로디핀정 5mg"),
            "diag_code": "",
        },
    }
    items = build_code_based_items(ds, REF, PRODUCT_HEALTH)
    codes = {it["code"] for it in items}
    # 정상 질환은 포함
    assert "K05" in codes
    # 비-KCD 항목은 차단
    assert not any("진찰료" in (it.get("disease") or "") for it in items)
    assert not any("PHARMA" in (it.get("code") or "") for it in items)
    assert not any("재진진찰료" in (it.get("code") or "") for it in items)


def test_non_disease_zcodes_excluded():
    """건강검진·선별검사·예방접종 Z코드는 질병으로 인정하지 않는다."""
    from filters import _is_valid_disease
    for code in ["Z00", "Z000", "Z11", "Z113", "Z23", "Z25"]:
        assert _is_valid_disease(code, "건강검진") is False, f"{code} 제외 실패"
    # 개인력·수술후상태 등 질병 관련 Z코드는 유지
    for code in ["Z85", "Z98", "Z95"]:
        assert _is_valid_disease(code, "") is True, f"{code} 잘못 제외됨"
