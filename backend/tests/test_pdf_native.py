"""SURIT-007: Gemini PDF 네이티브 첨부 회귀 테스트.

parse_single_pdf 가 PDF 바이너리를 결과에 포함하는지, 그리고 google-genai SDK
의 types.Part.from_bytes 가 PDF mime 으로 정상 동작하는지 검증한다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline.pdf_parser import parse_single_pdf


class _FakeUploadedFile:
    """parse_single_pdf 호환 mock — 가짜 바이트로 형식 검증용."""

    def __init__(self, content: bytes, name: str = "test.pdf"):
        self._content = content
        self.name = name
        self.filename = name

    def read(self):
        return self._content


def test_parse_single_pdf_returns_pdf_bytes_field():
    """결과 dict 에 pdf_bytes 키가 포함되며, 입력 바이트와 일치한다 (SURIT-007).

    파싱이 실패해도(가짜 PDF) 결과 구조와 pdf_bytes 필드는 보존돼야 한다.
    Gemini 네이티브 첨부 경로가 안정적으로 동작하려면 이 필드가 필수다.
    """
    raw = b"%PDF-1.4\n%fake content for shape test\n"
    f = _FakeUploadedFile(raw, "shape.pdf")
    result = parse_single_pdf(f, "")
    assert "pdf_bytes" in result
    assert result["pdf_bytes"] == raw
    assert "records" in result
    assert "parse_errors" in result
    assert "filename" in result


def test_gemini_pdf_part_construction():
    """google-genai SDK 가 PDF mime 으로 Part 생성을 지원한다 (SURIT-007).

    requirements.txt 의 google-genai==2.6.0 에서 PDF inline 첨부가 가능함을
    회귀로 보장한다. 향후 SDK 업그레이드 시 API 변경 감지용.
    """
    from google.genai import types

    pdf_bytes = b"%PDF-1.4\n%test\n"
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    assert part.inline_data is not None
    assert part.inline_data.mime_type == "application/pdf"
