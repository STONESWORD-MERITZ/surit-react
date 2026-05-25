"""SURIT-006: run_analysis 분해 헬퍼 단위 테스트.

run_analysis 에서 추출한 내부 헬퍼들이 독립적으로 올바르게 동작하는지 검증한다.
순수 리팩터링이므로 로직 변화는 없어야 한다.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import (
    _build_drug_change_text,
    _build_first_diag_lines,
    _build_presc_end_text,
    _build_system_prompt,
    _build_visit_count_lines,
)

HEALTH = "건강체/표준체 (일반심사)"
SIMPLE = "간편심사"


def test_build_system_prompt_health():
    """건강체 시스템 프롬프트에 4문항 기준·JSON 형식·기준일이 포함된다."""
    p = _build_system_prompt(HEALTH, "2026-05-25", "2026-02-24",
                             "2025-05-25", "2021-05-25", "2016-05-25")
    assert isinstance(p, str)
    assert "건강체/표준체 알릴의무 4문항" in p
    assert "flagged_items" in p
    assert "2026-05-25" in p


def test_build_system_prompt_simple_differs():
    """간편심사 프롬프트는 건강체와 다르며 Q4/Q5 사용 금지 문구를 쓴다."""
    args = ("2026-05-25", "2026-02-24", "2025-05-25", "2021-05-25", "2016-05-25")
    p_simple = _build_system_prompt(SIMPLE, *args)
    p_health = _build_system_prompt(HEALTH, *args)
    assert "간편심사" in p_simple
    assert "Q4/Q5는 절대 사용 금지" in p_simple
    assert p_simple != p_health


def test_build_drug_change_text_empty():
    """약 변경이 없으면 빈 문자열."""
    assert _build_drug_change_text([]) == ""


def test_build_drug_change_text_with_entry():
    """약 변경 항목이 있으면 질환명·변경유형이 텍스트에 포함된다."""
    summary = [{
        "name": "당뇨병", "change_type": "용량 증가",
        "stopped": [], "new": ["메트포르민1000mg"], "dose_increased": ["메트포르민"],
        "dose_decreased": [], "continued": [],
    }]
    txt = _build_drug_change_text(summary)
    assert "당뇨병" in txt and "용량 증가" in txt


def test_build_presc_end_text_empty():
    """처방 종료 상세가 없으면 빈 문자열."""
    assert _build_presc_end_text([], None, datetime(2026, 5, 25)) == ""


def test_build_first_diag_and_visit_lines_empty():
    """질병 통계가 비면 최초진단·통원집계 라인도 빈 리스트."""
    assert _build_first_diag_lines({}) == []
    assert _build_visit_count_lines({}, datetime(2016, 5, 25)) == []
