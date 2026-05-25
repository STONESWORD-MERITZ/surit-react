"""SURIT-005: 날짜 창 로직 중앙화 회귀 테스트.

_dts_in_range 는 helpers.py 의 단일 정본을 쓴다. filters.py 가 이를 import 하므로
filters._dts_in_range 와 helpers._dts_in_range 는 동일 객체여야 한다(중복 제거 확인).
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.helpers import _dts_in_range as _dts_helpers
from filters import _dts_in_range as _dts_filters


def test_dts_in_range_single_source():
    """filters 가 helpers 정본을 import → 같은 객체 (중복 구현 제거 확인)."""
    assert _dts_filters is _dts_helpers


def test_dts_in_range_includes_boundary():
    """경계일(since_dt 와 동일)은 포함된다 (>=)."""
    since = datetime(2021, 5, 25)
    assert _dts_helpers({"2021-05-25"}, since) == ["2021-05-25"]


def test_dts_in_range_excludes_before_boundary():
    """경계일 하루 전은 제외된다."""
    since = datetime(2021, 5, 25)
    assert _dts_helpers({"2021-05-24"}, since) == []


def test_dts_in_range_leap_year_span():
    """윤년(2024-02-29)이 낀 구간도 정상 필터링·정렬된다."""
    since = datetime(2022, 1, 1)
    dates = {"2021-12-31", "2022-01-01", "2024-02-29", "2025-06-30"}
    result = _dts_helpers(dates, since)
    assert result == ["2022-01-01", "2024-02-29", "2025-06-30"]
    assert "2021-12-31" not in result


def test_dts_in_range_ignores_invalid_dates():
    """파싱 불가 문자열·빈 값은 조용히 제외된다 (기존 동작 유지)."""
    since = datetime(2020, 1, 1)
    assert _dts_helpers({"", "not-a-date", "2023-03-03"}, since) == ["2023-03-03"]
