"""PDF 파서 — 빈/이미지 PDF 오류 메시지 회귀 테스트.

감사 지적: 정상 복호화됐으나 표가 없는 PDF(이미지 PDF 등)가 "비밀번호 확인"
안내로 잘못 떨어졌다. _empty_result_message 는 원인을 구분하되, 비밀번호
문제로 오인되지 않도록 "비밀번호"를 절대 언급하지 않는다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.pdf_parser import _empty_result_message


def test_image_pdf_message_mentions_image_not_password():
    """텍스트가 없는 PDF -> 이미지 PDF 안내, '비밀번호' 미언급."""
    msg = _empty_result_message("진료내역.pdf", 3, "")
    assert "이미지" in msg
    assert "비밀번호" not in msg


def test_format_mismatch_message_not_password():
    """텍스트는 있으나 표 인식 실패 -> 형식 확인 안내, '비밀번호' 미언급."""
    msg = _empty_result_message("기타.pdf", 2, "이건 진료내역이 아닌 일반 문서입니다")
    assert "진료 표" in msg
    assert "비밀번호" not in msg


def test_no_pages_message():
    """페이지가 없는 PDF -> 빈 PDF 안내."""
    msg = _empty_result_message("빈파일.pdf", 0, "")
    assert "빈 PDF" in msg
    assert "비밀번호" not in msg


def test_message_always_includes_filename():
    """어떤 파일이 문제인지 알 수 있도록 메시지에 파일명이 포함된다."""
    for n_pages, text in [(0, ""), (3, ""), (3, "텍스트있음")]:
        assert "내검사파일.pdf" in _empty_result_message("내검사파일.pdf", n_pages, text)
