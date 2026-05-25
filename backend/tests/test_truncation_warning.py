"""SURIT-003: 초대용량 PDF 잘림 감지 회귀 테스트.

ai_judgment._finalize_raw_text_for_gemini 의 잘림(줄 800 / 글자 30,000)을
analyzer 호출부에서 감지하는 로직을 검증한다. 잘림 로직 자체는 변경하지 않는다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import (
    _GEMINI_LINE_CAP,
    _build_truncation_warning,
    _is_gemini_input_truncated,
)


def _truncation_warning_for(file_lines: list[str], raw_text: str, filename: str = "내역.pdf"):
    if not _is_gemini_input_truncated(file_lines, raw_text):
        return _build_truncation_warning([])
    return _build_truncation_warning([filename])


def test_line_cap_truncation_detected():
    """filtered_lines 가 줄 한도를 넘으면 truncation_warning 을 만든다."""
    long_lines = ["진료기록 라인"] * (_GEMINI_LINE_CAP + 1)
    assert _is_gemini_input_truncated(long_lines, "짧은 본문") is True
    warning = _truncation_warning_for(long_lines, "짧은 본문", "초대용량.pdf")
    assert warning is not None
    assert "초대용량.pdf" in warning


def test_char_cap_truncation_detected():
    """raw_text 끝에 '... (truncated)' 표식이 있으면 truncation_warning 을 만든다."""
    assert _is_gemini_input_truncated(["한 줄"], "본문 일부\n... (truncated)") is True
    warning = _truncation_warning_for(["한 줄"], "본문 일부\n... (truncated)", "표식.pdf")
    assert warning is not None
    assert "표식.pdf" in warning


def test_no_truncation_when_within_limits():
    """줄 수가 한도 이하이고 표식도 없으면 truncation_warning 이 없다."""
    assert _is_gemini_input_truncated(["라인"] * 10, "정상 본문") is False
    assert _is_gemini_input_truncated([], "") is False
    assert _truncation_warning_for(["라인"] * 10, "정상 본문") is None
    assert _truncation_warning_for([], "") is None


def test_warning_none_when_no_truncated_files():
    """잘린 파일이 없으면 경고는 None 이다 (응답 필드 null)."""
    assert _build_truncation_warning([]) is None


def test_warning_message_lists_truncated_files():
    """잘린 파일이 있으면 경고 문구에 안내와 해당 파일명이 포함된다."""
    msg = _build_truncation_warning(["내역A.pdf", "내역B.pdf"])
    assert msg is not None
    assert "PDF 용량" in msg
    assert "내역A.pdf" in msg and "내역B.pdf" in msg
