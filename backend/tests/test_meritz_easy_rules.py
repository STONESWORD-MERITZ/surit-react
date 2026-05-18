"""
메리츠화재 간편보험 예외질환 룰 회귀 테스트.

평가 축:
  - 경과기간 (치료종결일 + 경과일수 vs 청약일)
  - 입원기준 (일수 / 횟수, -1 = 제한없음)
  - 수술기준 (0=비수술, N=N회까지, -1=제한없음)
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from meritz_easy_rules import evaluate_meritz_easy, evaluate_disease, find_rule

REF = datetime(2026, 5, 12)


def _disease(*, code="K05", name="만성치주염", first="", latest="",
             inpatients=(), inpatient_days=None, surgeries=()):
    s = {
        "diag_code":         code,
        "name":              name,
        "first_date":        first or "2099-12-31",
        "latest_date":       latest or "2000-01-01",
        "visit_dates":       set(),
        "inpatient_dates":   set(inpatients),
        "surgery_dates":     set(surgeries),
        "surgeries":         set(),
        "_inpatient_days_map": {
            d: (inpatient_days[d] if inpatient_days and d in inpatient_days else 1)
            for d in inpatients
        },
        "hospitals":         set(),
        "_daily_facts":      {},
        "med_dates_basic":   {},
        "med_dates_pharma":  {},
        "drug_names_in_90":  set(),
        "drug_names_before_90": set(),
        "tests_found":       set(),
        "procedures":        set(),
        "procedure_dates":   set(),
        "surgery_suspected_names": set(),
        "surgery_suspected_dates": set(),
        "chojin_count": 0,
        "jaejin_count": 0,
        "drug_change_in_3m": False,
        "has_pharma":  False,
    }
    return s


# ── find_rule: 룰 룩업 ──────────────────────────────────────────

def test_find_rule_basic():
    assert find_rule("K05") is not None       # K00~K14 범위
    assert find_rule("Z53") is not None       # Z53 단독
    assert find_rule("INVALID") is None
    assert find_rule("") is None


def test_find_rule_returns_proper_tuple():
    r = find_rule("K05")
    assert r is not None
    start, end, elapsed, h_days, h_cnt, surg = r
    assert elapsed == 7
    assert h_days == -1   # 입원일수 제한 없음
    assert h_cnt  == -1   # 입원횟수 제한 없음
    assert surg   == -1   # 수술 제한 없음


# ── evaluate_disease: 단일 질환 판정 ────────────────────────────

def test_evaluate_disease_no_inpatient_no_surgery_passes():
    """입원·수술 전혀 없는 K05 (제한없음 룰) → 인수 가능"""
    s = _disease(code="K05", first="2024-01-01", latest="2024-01-01")
    r = evaluate_disease("K05", s, REF)
    assert r is not None
    assert r["eligible"] is True


def test_evaluate_disease_elapsed_period_fail():
    """치료 종결 후 경과기간 미달 → 인수 불가"""
    # 청약일 2026-05-12 / 기준 7일 / 최종 진료 2026-05-10 (2일 경과)
    s = _disease(code="K05", first="2026-05-10", latest="2026-05-10")
    r = evaluate_disease("K05", s, REF)
    assert r is not None
    assert r["elapsed_ok"] is False
    assert r["eligible"] is False


def test_evaluate_disease_inpatient_days_exceed():
    """A01 범위 (10일/2회/비수술) 입원 11일 → 입원일수 초과 → 불가"""
    s = _disease(code="A01", first="2023-01-01", latest="2023-01-11",
                 inpatients=["2023-01-01"],
                 inpatient_days={"2023-01-01": 11})
    r = evaluate_disease("A01", s, REF)
    assert r is not None
    assert r["hosp_ok"] is False
    assert r["eligible"] is False


def test_evaluate_disease_inpatient_count_exceed():
    """A01 입원 3회 → 횟수 초과 → 불가"""
    s = _disease(code="A01", first="2022-01-01", latest="2024-05-01",
                 inpatients=["2022-01-01", "2023-06-01", "2024-05-01"],
                 inpatient_days={"2022-01-01": 1, "2023-06-01": 1, "2024-05-01": 1})
    r = evaluate_disease("A01", s, REF)
    assert r is not None
    assert r["hosp_ok"] is False
    assert r["eligible"] is False


def test_evaluate_disease_surgery_disallowed():
    """A01 (비수술 룰, surg=0) 인데 수술 1회 → 수술기준 실패"""
    s = _disease(code="A01", first="2022-01-01", latest="2022-01-05",
                 inpatients=["2022-01-01"],
                 inpatient_days={"2022-01-01": 1},
                 surgeries=["2022-01-03"])
    r = evaluate_disease("A01", s, REF)
    assert r is not None
    assert r["surgery_ok"] is False
    assert r["eligible"] is False


def test_evaluate_disease_surgery_within_limit():
    """수술 허용 룰(D11~D136: surg=2)에서 수술 1회 → 통과"""
    s = _disease(code="D11", first="2020-01-01", latest="2020-01-05",
                 inpatients=["2020-01-01"],
                 inpatient_days={"2020-01-01": 3},
                 surgeries=["2020-01-03"])
    r = evaluate_disease("D11", s, REF)
    assert r is not None
    assert r["surgery_ok"] is True
    assert r["eligible"] is True


def test_evaluate_disease_unlimited_rule():
    """K05 (모든 제한 없음) → 다수 입원/수술도 통과 (경과기간만 충족)"""
    s = _disease(code="K05", first="2020-01-01", latest="2020-02-01",
                 inpatients=["2020-01-01", "2020-01-10", "2020-02-01"],
                 inpatient_days={"2020-01-01": 30, "2020-01-10": 30, "2020-02-01": 30},
                 surgeries=["2020-01-05", "2020-01-15"])
    r = evaluate_disease("K05", s, REF)
    assert r is not None
    assert r["eligible"] is True


def test_evaluate_disease_unknown_code_returns_none():
    """룰 없는 코드 → None 반환"""
    s = _disease(code="Z9999")
    assert evaluate_disease("Z9999", s, REF) is None


# ── evaluate_meritz_easy: 전체 흐름 ─────────────────────────────

def test_evaluate_meritz_easy_zero_diseases():
    out = evaluate_meritz_easy({}, REF)
    assert out["meritz_easy_eligible"] is True
    assert out["exception_diseases_count"] == 0


def test_evaluate_meritz_easy_within_5_limit():
    """예외질환 3개 이내 → 인수 가능 (K00~K14 범위 입원이력 1건씩, 횟수·일수 제한없음)"""
    ds = {
        "K05": _disease(code="K05", first="2024-01-01", latest="2024-01-01",
                        inpatients=["2024-01-01"], inpatient_days={"2024-01-01": 1}),
        "K06": _disease(code="K06", first="2024-01-01", latest="2024-01-01",
                        inpatients=["2024-01-01"], inpatient_days={"2024-01-01": 1}),
        "K07": _disease(code="K07", first="2024-01-01", latest="2024-01-01",
                        inpatients=["2024-01-01"], inpatient_days={"2024-01-01": 1}),
    }
    out = evaluate_meritz_easy(ds, REF)
    assert out["meritz_easy_eligible"] is True
    assert out["exception_diseases_count"] == 3
    assert len(out["exception_diseases"]) == 3


def test_evaluate_meritz_easy_outpatient_only_skipped():
    """외래(통원)만 있는 질환은 간편 2번 평가 대상 아님 → 카운트 0"""
    ds = {
        "K05": _disease(code="K05", first="2024-01-01", latest="2024-01-01"),
    }
    out = evaluate_meritz_easy(ds, REF)
    # 입원·수술 기록 없음 → 평가 스킵 → exception/rejected 모두 0
    assert out["exception_diseases_count"] == 0
    assert out["meritz_easy_eligible"] is True


def test_evaluate_meritz_easy_unknown_codes_skipped():
    """룰 테이블에 없는 KCD 코드는 평가 스킵"""
    ds = {
        "Z9999": _disease(code="Z9999", first="2024-01-01", latest="2024-01-01"),
    }
    out = evaluate_meritz_easy(ds, REF)
    by_code = lambda lst: {d.get("code") for d in lst}
    assert "Z9999" not in by_code(out["exception_diseases"])
    assert "Z9999" not in by_code(out["rejected_diseases"])
