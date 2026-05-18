"""
analyzer.py 결정론적 통합 테스트.
Gemini API (analyze_single_pdf, _call_medical_judgment) 는 mock.
parse_single_pdf 도 fixture records 반환으로 교체.
"""
import asyncio
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import analyzer


# ── 가짜 PDF 객체 ──────────────────────────────────────────────

class _FakePdfFile:
    """run_analysis 가 받는 PDF 입력 mock — parse_single_pdf 단계는 우회"""
    def __init__(self, records: list, name: str = "fake.pdf"):
        self.name = name
        self._records = records

    def read(self) -> bytes:
        return b""


def _basic_row(date_str: str, code: str, name: str,
               hospital: str = "A의원", in_out: str = "외래", m_days: int = 1) -> dict:
    return {
        "_ftype": "basic", "_fname": "fake.pdf",
        "진료시작일":   date_str,
        "주상병코드":   code,
        "주상병명":     name,
        "병·의원":      hospital,
        "입원/외래":    in_out,
        "내원일수":     str(m_days),
        "진단과":       "내과",
    }


def _pharma_row(date_str: str, drug: str, m_days: int) -> dict:
    return {
        "_ftype": "pharma", "_fname": "fake.pdf",
        "진료시작일":   date_str,
        "약품명":       drug,
        "처방/조제":    "처방",
        "투약일수":     str(m_days),
    }


# ── Mock 헬퍼 ──────────────────────────────────────────────────

def _mock_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI Gemini 관련 비동기 함수를 mock으로 교체"""
    async def fake_single(parsed: dict, *_a, **_kw) -> dict:
        return {
            "filename":       parsed.get("filename", "fake.pdf"),
            "ai_result":      {"flagged_items": [], "summary": ""},
            "retry_warnings": [],
            "error":          None,
        }

    async def fake_med(*_a, **_kw) -> dict:
        return {"additional_tests": {}, "treatment_ongoing": {}}

    monkeypatch.setattr(analyzer, "analyze_single_pdf", fake_single)
    monkeypatch.setattr(analyzer, "_call_medical_judgment", fake_med)


def _mock_parse(monkeypatch: pytest.MonkeyPatch, records: list) -> None:
    """parse_single_pdf 를 fixture records 반환으로 교체"""
    def fake_parse(uploaded, birthdate_pw: str) -> dict:
        return {
            "filename":     getattr(uploaded, "name", "fake.pdf"),
            "records":      records,
            "parse_errors": [],
        }

    monkeypatch.setattr(analyzer, "parse_single_pdf", fake_parse)


# ── 시나리오 1: 10년 이내 통원 7회 이상 → Q3 ──────────────────

def test_run_analysis_q3_visit_7plus(monkeypatch: pytest.MonkeyPatch) -> None:
    """동일 K05 통원 8회 → Q3 에 포함되어야 한다"""
    records = [_basic_row(f"2025-{m:02d}-15", "AK05", "치주염") for m in range(1, 9)]
    _mock_parse(monkeypatch, records)
    _mock_ai(monkeypatch)

    result = asyncio.run(analyzer.run_analysis(
        active_files=[_FakePdfFile(records)],
        product_type="건강체/표준체 (일반심사)",
        reference_date=date(2026, 5, 12),
        birthdate_pw="",
        api_key="fake",
    ))

    reports = result["summary_reports"]
    q3_keys = [k for k in reports if "3번" in k]
    assert q3_keys, f"Q3 키 없음: {list(reports.keys())}"
    codes = {item["code"] for item in reports[q3_keys[0]]}
    assert "K05" in codes


# ── 시나리오 2: 3개월 내 입원 → Q1 ───────────────────────────

def test_run_analysis_q1_recent_inpatient(monkeypatch: pytest.MonkeyPatch) -> None:
    """기준일(2026-05-12) 3개월 이내 입원 → Q1 에 포함되어야 한다"""
    records = [
        _basic_row("2026-04-10", "AN840", "자궁용종",
                   hospital="B병원", in_out="입원", m_days=3),
    ]
    _mock_parse(monkeypatch, records)
    _mock_ai(monkeypatch)

    result = asyncio.run(analyzer.run_analysis(
        active_files=[_FakePdfFile(records)],
        product_type="건강체/표준체 (일반심사)",
        reference_date=date(2026, 5, 12),
        birthdate_pw="",
        api_key="fake",
    ))

    q1_keys = [k for k in result["summary_reports"] if "1번" in k]
    assert q1_keys, f"Q1 키 없음: {list(result['summary_reports'].keys())}"
    codes = {it["code"] for it in result["summary_reports"][q1_keys[0]]}
    assert "N840" in codes


# ── 시나리오 3: 비-질병 항목(진찰료) 결과 카드에서 차단 ─────────

def test_run_analysis_filters_non_disease(monkeypatch: pytest.MonkeyPatch) -> None:
    """진찰료·조제료 같은 비-질병 청구 항목은 summary_reports 카드에 들어오면 안 된다"""
    records = [
        _basic_row("2025-06-01", "AJ209", "급성기관지염"),
        # KCD 코드 없는 detail 행(진찰료) — disease_stats 진입 금지
        {
            "_ftype": "detail", "_fname": "fake.pdf",
            "진료시작일": "2025-06-01",
            "진료내역":   "재진진찰료",
            "코드명":     "AA254",
            "병·의원":    "A의원",
        },
    ]
    _mock_parse(monkeypatch, records)
    _mock_ai(monkeypatch)

    result = asyncio.run(analyzer.run_analysis(
        active_files=[_FakePdfFile(records)],
        product_type="건강체/표준체 (일반심사)",
        reference_date=date(2026, 5, 12),
        birthdate_pw="",
        api_key="fake",
    ))

    all_names = [
        it.get("name", "")
        for items in result["summary_reports"].values()
        for it in items
    ]
    for noisy in ("진찰료", "조제료", "주사료", "약국관리료"):
        assert all(noisy not in n for n in all_names), \
            f"비-질병 항목 누락 차단 실패: '{noisy}' in {all_names}"
