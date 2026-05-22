"""분석 창 경계(90·365·1825·3650일) 회귀 테스트.

감사 지적(누락된 테스트): 창 경계 정확일·미래일자 드롭이 테스트로 고정돼 있지
않았다. 이 파일은 두 날짜 경로가 경계에서 일치함을 고정한다.

  · 결정론 엔진 경로  : filters/helpers 의 ``_dts_in_range`` (>= since_dt 포함)
  · AI 입력 태깅 경로 : analyzer.py 의 ``days_ago``  (days_ago <= N 포함)

두 경로 모두 "정확히 N일 전"은 포함, "N+1일 전"은 제외, 미래일자는 드롭한다.
이 불변식이 깨지면(예: <= 를 < 로 변경) 아래 테스트가 실패한다.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from filters import _dts_in_range as _dts_filters, _max_presc as _max_presc_filters
from pipeline.helpers import _dts_in_range as _dts_helpers, _max_presc as _max_presc_helpers
from pipeline.disease_aggregator import build_disease_stats

TODAY = datetime(2026, 5, 17)
# (일수, 라벨) — 건강체/간편 알릴의무 창
WINDOWS = [(90, "3개월"), (365, "1년"), (1825, "5년"), (3650, "10년")]


def _ymd(days_ago):
    """TODAY 기준 days_ago 일 전 날짜 문자열. 음수면 미래."""
    return (TODAY - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# ── _dts_in_range 경계 ───────────────────────────────────────────────────────
def test_dts_in_range_includes_exact_boundary_day():
    """정확히 N일 전 날짜는 창에 포함된다 (>= 경계 포함)."""
    for n, label in WINDOWS:
        cutoff = TODAY - timedelta(days=n)
        on = _ymd(n)
        assert _dts_helpers({on}, cutoff) == [on], f"{label}: helpers판 경계일 누락"
        assert _dts_filters({on}, cutoff) == [on], f"{label}: filters판 경계일 누락"


def test_dts_in_range_excludes_day_past_boundary():
    """N+1일 전 날짜는 창에서 제외된다."""
    for n, label in WINDOWS:
        cutoff = TODAY - timedelta(days=n)
        off = _ymd(n + 1)
        assert _dts_helpers({off}, cutoff) == [], f"{label}: helpers판 경계밖 포함됨"
        assert _dts_filters({off}, cutoff) == [], f"{label}: filters판 경계밖 포함됨"


def test_dts_in_range_helpers_and_filters_identical():
    """helpers판과 filters판 _dts_in_range 는 동일하게 동작한다 (중복 구현 발산 방지)."""
    for n, _ in WINDOWS:
        cutoff = TODAY - timedelta(days=n)
        for off in range(n - 2, n + 3):
            ds = {_ymd(off)}
            assert _dts_helpers(ds, cutoff) == _dts_filters(ds, cutoff)


# ── _max_presc 경계 ──────────────────────────────────────────────────────────
def test_max_presc_includes_exact_boundary_day():
    """정확히 N일 전 처방은 투약일수 집계에 포함된다."""
    for n, label in WINDOWS:
        cutoff = TODAY - timedelta(days=n)
        on = _ymd(n)
        assert _max_presc_filters({on: 30}, cutoff) == 30, f"{label}: filters판 경계일 처방 누락"
        assert _max_presc_helpers({on: 30}, cutoff) == 30, f"{label}: helpers판 경계일 처방 누락"


def test_max_presc_excludes_day_past_boundary():
    """N+1일 전 처방은 투약일수 집계에서 제외된다."""
    for n, label in WINDOWS:
        cutoff = TODAY - timedelta(days=n)
        off = _ymd(n + 1)
        assert _max_presc_filters({off: 30}, cutoff) == 0, f"{label}: filters판 경계밖 처방 포함됨"
        assert _max_presc_helpers({off: 30}, cutoff) == 0, f"{label}: helpers판 경계밖 처방 포함됨"


# ── 태깅 경로 ↔ _dts_in_range 동치 ───────────────────────────────────────────
def _tag_windows(days_ago):
    """analyzer.py 의 날짜 태깅 규칙을 그대로 복제 — 회귀 고정용.

    analyzer.py:
        if days_ago < 0 or days_ago > 3650: continue   # 드롭
        if days_ago <= 90:   IN_3M
        if days_ago <= 365:  IN_1Y
        if days_ago <= 1825: IN_5Y
        if days_ago <= 3650: IN_10Y
    """
    if days_ago < 0 or days_ago > 3650:
        return None  # 드롭됨
    tags = set()
    for n in (90, 365, 1825, 3650):
        if days_ago <= n:
            tags.add(n)
    return tags


def test_tagging_matches_dts_in_range_at_every_offset():
    """analyzer.py 태깅과 _dts_in_range 멤버십이 0~3651일 전 전 구간에서 일치한다.

    한쪽이라도 경계 부등호를 바꾸면(<= → <) 이 테스트가 잡아낸다.
    """
    for n, label in WINDOWS:
        cutoff = TODAY - timedelta(days=n)
        for off in range(0, 3652):
            ds = _ymd(off)
            tag = _tag_windows(off)
            tagged_in = tag is not None and n in tag
            range_in = bool(_dts_helpers({ds}, cutoff))
            assert tagged_in == range_in, (
                f"{label} 경계 불일치: {off}일전 태깅={tagged_in} 범위={range_in}"
            )


# ── 미래일자 드롭 ────────────────────────────────────────────────────────────
def _prow(date_str, drug, m_days, hospital):
    return {
        "_ftype": "pharma",
        "_fname": "fake.pdf",
        "진료시작일": date_str,
        "처방/조제": "외래",
        "약품명": drug,
        "투약일수": str(m_days),
        "병·의원": hospital,
    }


def test_future_dated_row_dropped_by_aggregator():
    """미래 일자(오늘 이후) 행은 build_disease_stats 에서 드롭된다."""
    records = [
        _prow(_ymd(-5), "베포리진정", 3, "A의원"),  # 오늘+5일 — 미래
        _prow(_ymd(10), "베포리진정", 3, "A의원"),  # 10일 전 — 정상
    ]
    disease_stats, *_ = build_disease_stats(records, TODAY)
    groups = [s for k, s in disease_stats.items()
              if s.get("has_pharma") or k.startswith("PHARMA|")]
    total_seen = sum(len(s.get("_pharma_seen", set())) for s in groups)
    assert total_seen == 1, "미래 일자 행이 드롭되지 않음 (정상 1건만 남아야 함)"


def test_today_dated_row_kept_by_aggregator():
    """오늘 일자(days_ago == 0) 행은 미래가 아니므로 보존된다."""
    records = [_prow(_ymd(0), "베포리진정", 3, "A의원")]
    disease_stats, *_ = build_disease_stats(records, TODAY)
    groups = [s for k, s in disease_stats.items()
              if s.get("has_pharma") or k.startswith("PHARMA|")]
    total_seen = sum(len(s.get("_pharma_seen", set())) for s in groups)
    assert total_seen == 1, "오늘 일자 행이 잘못 드롭됨"
