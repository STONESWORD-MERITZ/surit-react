"""SURIT-004: 윤년 컷오프 보정 회귀 테스트.

5년/10년 분석 창을 고정 일수(1825/3650) 대신 달력 연도 기준으로 계산한다.
helpers._subtract_years 와 filters._subtract_years(인라인 동본)를 검증한다.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.helpers import _subtract_years
from filters import _subtract_years as _subtract_years_filters

FIXED_5Y_DAYS = 365 * 5
FIXED_10Y_DAYS = 365 * 10


def test_subtract_years_calendar_based():
    """5년/10년 전 = 같은 월·일, 연도만 차감."""
    ref = datetime(2026, 5, 25)
    assert _subtract_years(ref, 5) == datetime(2021, 5, 25)
    assert _subtract_years(ref, 10) == datetime(2016, 5, 25)


def test_subtract_years_longer_than_fixed_days():
    """달력 기준 5년/10년 컷오프가 고정 1825/3650일보다 더 과거다.

    윤년이 끼면 5년=1826일·10년=3652일이라, 고정 일수 컷오프는 실제
    경계보다 늦다(창이 2~3일 짧다). 달력 기준이 더 이른 날짜가 된다.
    """
    ref = datetime(2026, 5, 25)
    cal_5y, fixed_5y = _subtract_years(ref, 5), ref - timedelta(days=FIXED_5Y_DAYS)
    assert cal_5y < fixed_5y
    assert (fixed_5y - cal_5y).days in (1, 2)

    cal_10y, fixed_10y = _subtract_years(ref, 10), ref - timedelta(days=FIXED_10Y_DAYS)
    assert cal_10y < fixed_10y
    assert (fixed_10y - cal_10y).days in (2, 3)


def test_subtract_years_leap_day_reference():
    """2/29 기준일: 대상 연도가 윤년이면 2/29 유지, 아니면 2/28로 보정."""
    leap_ref = datetime(2024, 2, 29)
    assert _subtract_years(leap_ref, 4) == datetime(2020, 2, 29)   # 2020 윤년
    assert _subtract_years(leap_ref, 1) == datetime(2023, 2, 28)   # 2023 비윤년
    assert _subtract_years(leap_ref, 5) == datetime(2019, 2, 28)   # 2019 비윤년


def test_subtract_years_boundary_inclusive_semantics():
    """경계일 자체는 창에 포함(>=)되어야 한다."""
    ref = datetime(2026, 5, 25)
    cutoff = _subtract_years(ref, 5)
    assert datetime(2021, 5, 25) >= cutoff   # 정확히 5년 전 → 창 안
    assert datetime(2021, 5, 24) < cutoff    # 하루 전 → 창 밖


def test_filters_inline_matches_helpers():
    """filters.py 인라인 _subtract_years 가 helpers 동본과 동일 결과."""
    for ref in (datetime(2026, 5, 25), datetime(2024, 2, 29), datetime(2020, 2, 29)):
        for yrs in (5, 10):
            assert _subtract_years_filters(ref, yrs) == _subtract_years(ref, yrs)
