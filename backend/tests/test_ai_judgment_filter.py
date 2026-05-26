"""SURIT-ROLLBACK-001: ai_judgment._strengthen_filter 회귀 테스트.

318p 같은 대용량 PDF에서 잘림 상한 내에 실제 진료 데이터가 더 많이 들어가도록
반복 헤더·연속 중복·짧은 노이즈 줄을 제거하는 동작을 검증한다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.ai_judgment import (
    _finalize_raw_text_for_gemini,
    _has_signal,
    _looks_like_repeated_header,
    _strengthen_filter,
)


def test_strengthen_filter_removes_repeated_headers():
    """반복되는 표 헤더(요양기관명·상병코드 등 키워드 2개↑)는 제거된다."""
    lines = [
        "요양기관명 상병코드 진료시작일",                # 헤더 3개 — 제거
        "2024.03.15 ABC병원 J20 급성기관지염",            # 데이터 — 보존
        "요양기관명 상병코드",                            # 헤더 2개 — 제거
        "2024.04.02 XYZ의원 K29 위염 처방 7일",            # 데이터 — 보존
        "처방내역 조제내역 투약일수",                      # 헤더 3개 — 제거
    ]
    out = _strengthen_filter(lines)
    assert "2024.03.15 ABC병원 J20 급성기관지염" in out
    assert "2024.04.02 XYZ의원 K29 위염 처방 7일" in out
    for kept in out:
        assert not _looks_like_repeated_header(kept)


def test_strengthen_filter_removes_consecutive_duplicates():
    """직전과 동일한 줄(연속 중복)은 제거된다 (페이지 푸터 반복 등)."""
    lines = [
        "2024.05.01 A의원 J20 급성기관지염",
        "2024.05.01 A의원 J20 급성기관지염",   # 연속 중복 — 제거
        "2024.05.01 A의원 J20 급성기관지염",   # 연속 중복 — 제거
        "2024.05.02 B의원 K29 위염",
        "2024.05.01 A의원 J20 급성기관지염",   # 중간에 다른 줄 → 다시 보존
    ]
    out = _strengthen_filter(lines)
    assert out.count("2024.05.01 A의원 J20 급성기관지염") == 2
    assert "2024.05.02 B의원 K29 위염" in out


def test_strengthen_filter_removes_noise_lines():
    """신호(숫자·날짜·코드) 없는 짧은 노이즈는 제거, 의미 있는 줄은 보존."""
    lines = [
        "",                                       # 빈 줄 — 제거
        "  ",                                     # 공백만 — 제거
        "a",                                      # 1자 — 제거
        "ab",                                     # 2자 — 제거
        "기타",                                    # 짧고 신호 없음 — 제거
        "2024.06.01 J20",                         # 짧지만 신호 있음 — 보존
        "급성기관지염 환자 진료내역 입니다",          # 길지만 신호 없음 — 보존(>=10)
        "2024.07.10 ABC의원 K29 위염 처방",        # 데이터 — 보존
    ]
    out = _strengthen_filter(lines)
    assert "" not in out
    assert "a" not in out
    assert "ab" not in out
    assert "기타" not in out
    assert "2024.06.01 J20" in out
    assert "급성기관지염 환자 진료내역 입니다" in out
    assert "2024.07.10 ABC의원 K29 위염 처방" in out


def test_has_signal_detects_dates_codes_numbers():
    """날짜·상병코드·3자리 숫자 중 하나라도 있으면 신호로 인식."""
    assert _has_signal("2024.03.15 진료")           # 날짜
    assert _has_signal("J20 급성기관지염")            # 상병코드
    assert _has_signal("처방일수 365일")             # 3자리 숫자
    assert not _has_signal("기타 항목")              # 신호 없음
    assert not _has_signal("")                       # 빈 문자열


def test_finalize_raw_text_applies_strengthen_filter():
    """_finalize_raw_text_for_gemini 가 _strengthen_filter 를 거친다."""
    lines = [
        "요양기관명 상병코드 진료시작일",     # 헤더 — 제거 대상
        "2024.03.15 ABC병원 J20 급성기관지염",
        "2024.03.15 ABC병원 J20 급성기관지염",   # 연속 중복 — 제거 대상
        "2024.04.02 XYZ의원 K29 위염 처방 7일",
        "기타",                                   # 노이즈 — 제거 대상
    ]
    text = _finalize_raw_text_for_gemini(
        filtered_lines=lines,
        visit_count_lines=[],
        cross_surgery_hints=[],
        first_diag_lines=[],
        drug_change_text="",
        presc_end_text="",
    )
    assert "요양기관명 상병코드 진료시작일" not in text
    assert text.count("2024.03.15 ABC병원 J20 급성기관지염") == 1
    assert "2024.04.02 XYZ의원 K29 위염 처방 7일" in text
    assert "\n기타\n" not in text
