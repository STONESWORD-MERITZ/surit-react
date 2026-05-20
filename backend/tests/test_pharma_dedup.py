"""처방조제 중복 행 차단 회귀 테스트."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.disease_aggregator import build_disease_stats


def _row(date_str, gubun, drug, m_days):
    return {
        "_ftype": "pharma",
        "_fname": "fake.pdf",
        "진료시작일": date_str,
        "처방/조제": gubun,
        "약품명": drug,
        "투약일수": str(m_days),
    }


def test_pharma_dispensing_rows_skipped():
    """같은 날짜·약품의 '외래'(처방) + '처방조제'(조제) 두 행 중 조제 행은 스킵."""
    today = datetime(2026, 5, 12)
    # today 기준 90일 이내 날짜 사용 (2026-04-01 = 41일 전)
    records = [
        _row("2026-04-01", "외래",     "베포리진정", 3),
        _row("2026-04-01", "처방조제", "베포리진정", 3),  # 약국 조제 — 스킵돼야
        _row("2026-04-01", "외래",     "케이스틴정", 3),
        _row("2026-04-01", "처방조제", "케이스틴정", 3),  # 약국 조제 — 스킵돼야
    ]
    disease_stats, *_ = build_disease_stats(records, today)

    pharma_groups = [s for k, s in disease_stats.items() if s.get("has_pharma") or k.startswith("PHARMA|")]
    all_drugs: set = set()
    for s in pharma_groups:
        all_drugs |= s.get("drug_names_in_90", set())
    assert all_drugs == {"베포리진정", "케이스틴정"}, f"중복 차단 실패: {all_drugs}"

    # _pharma_seen 에 각 (날짜, 약품) 쌍이 한 번만 기록됐는지 확인
    total_seen = sum(len(s.get("_pharma_seen", set())) for s in pharma_groups)
    assert total_seen == 2, f"처방 행이 2건이어야 함 (외래 2건), 실제: {total_seen}"


def test_pharma_prescription_outpatient_passes():
    """'외래' 값만 있는 정상 처방은 통과해야 한다."""
    today = datetime(2026, 5, 12)
    records = [_row("2026-04-01", "외래", "베포리진정", 3)]
    disease_stats, *_ = build_disease_stats(records, today)

    pharma_groups = [s for k, s in disease_stats.items() if s.get("has_pharma") or k.startswith("PHARMA|")]
    assert any("베포리진정" in s.get("drug_names_in_90", set()) for s in pharma_groups)


def test_med_days_takes_max_not_sum():
    """동일 질병 여러 처방 → 합산 아닌 최대값"""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
    from pipeline.helpers import _max_presc
    since = datetime(2016, 1, 1)
    # 같은 질병에 8/22 3일, 9/10 5일, 10/01 30일 처방
    flat = {"2025-08-22": 3, "2025-09-10": 5, "2025-10-01": 30}
    assert _max_presc(flat, since) == 30          # 합산(38) 아님

    # episode 중첩형도 max
    nested = {"2025-08-22": {"A의원": 3, "B약국": 3}, "2025-10-01": {"C의원": 30}}
    assert _max_presc(nested, since) == 30         # 합산(36) 아님


def test_pure_dispensing_only_rows_skipped():
    """'조제' 값만 있는 순수 약국 행도 스킵돼야 한다."""
    today = datetime(2026, 5, 12)
    records = [_row("2026-04-01", "조제", "베포리진정", 3)]
    disease_stats, *_ = build_disease_stats(records, today)

    pharma_groups = [s for k, s in disease_stats.items() if s.get("has_pharma") or k.startswith("PHARMA|")]
    all_drugs: set = set()
    for s in pharma_groups:
        all_drugs |= s.get("drug_names_in_90", set())
    assert "베포리진정" not in all_drugs, "순수 조제 행이 통과됨"
