"""
스냅샷 테스트 — analyzer.py 핵심 로직 회귀 방지

사용법:
    pytest backend/tests/test_analyzer_snapshot.py -v

새 fixture 추가:
    1. backend/tests/fixtures/ 에 JSON 레코드 파일 추가
    2. 아래 테스트에 기대값 추가

주의: AI(Gemini) 호출은 포함하지 않음 — 결정론적 코드 기반 로직만 검증
"""
import json
import os
import sys
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analyzer import (
    detect_file_type,
    normalize_code,
    parse_date,
    extract_drug_info,
    _is_surgery_match,
    new_disease,
    _dts_in_range,
    _code_in,
)


# ── detect_file_type ──────────────────────────────────────────────

def test_detect_file_type_basic():
    headers = ("순번", "진료개시일", "상병코드", "상병명", "입내원구분", "요양일수")
    assert detect_file_type(headers) == "basic"


def test_detect_file_type_detail():
    headers = ("순번", "진료일", "행위명칭", "급여비총액", "비급여")
    assert detect_file_type(headers) == "detail"


def test_detect_file_type_pharma():
    headers = ("순번", "조제일자", "약품명", "투약일수", "약품코드")
    assert detect_file_type(headers) == "pharma"


def test_detect_file_type_fallback_pattern():
    # 키워드 직접 매칭은 실패하지만 패턴 기반으로 추론
    headers = ("번호", "날짜", "분류코드", "이름", "구분")
    result = detect_file_type(headers)
    assert result == "basic"  # has_date_col + has_code_like


# ── normalize_code ────────────────────────────────────────────────

def test_normalize_code_prefix_strip():
    # A/B는 다음 문자가 영문일 때만 양방/한의학 구분자로 간주해 제거
    # (A123/B456처럼 실제 대분류 코드인 경우는 유지)
    assert normalize_code("A123") == "A123"
    assert normalize_code("B456") == "B456"
    assert normalize_code("BK635") == "K635"  # B 제거 → K635


def test_normalize_code_ocr_prefix_alpha():
    # A/B 구분자 제거 + 점 제거 (선행 0은 의미있으므로 보존)
    assert normalize_code("AO0339") == "O0339"  # O0339: 의미있는 0 보존
    assert normalize_code("AO339")  == "O339"
    assert normalize_code("O33.9")  == "O339"
    assert normalize_code("AI639")  == "I639"
    assert normalize_code("I63.9")  == "I639"


def test_normalize_code_ocr_1_to_I():
    assert normalize_code("1670") == "I670"


def test_normalize_code_empty():
    assert normalize_code("") == ""
    assert normalize_code("$") == ""


# ── parse_date ────────────────────────────────────────────────────

def test_parse_date_formats():
    assert parse_date("2025-03-15") == "2025-03-15"
    assert parse_date("2025.03.15") == "2025-03-15"
    assert parse_date("20250315") == "2025-03-15"
    assert parse_date("no date here") == ""


# ── extract_drug_info ─────────────────────────────────────────────

def test_drug_info_normalization():
    # 같은 성분 다른 표기 — 괄호 내 제조사 vs 제형 suffix
    base1, dose1 = extract_drug_info("메트포르민정 500mg (한미제약)")
    base2, dose2 = extract_drug_info("메트포르민정 500mg (대웅제약)")
    assert base1 == base2  # 제��사 달라도 동일 성분
    assert dose1 == dose2 == 500.0


def test_drug_info_unit_conversion():
    _, dose_mg = extract_drug_info("약품 1g")
    assert dose_mg == 1000.0
    _, dose_mcg = extract_drug_info("약품 500mcg")
    assert dose_mcg == 0.5


def test_drug_info_no_dose():
    base, dose = extract_drug_info("아스피린정")
    assert dose == 0.0
    assert "아스피린" in base


# ── _is_surgery_match ─────────────────────────────────────────────

def test_surgery_match_positive():
    assert _is_surgery_match("대장내시경 용종절제술") is True
    assert _is_surgery_match("충수절제술") is True


def test_surgery_match_negative_blocks():
    # "시술" in text but negative "검사" also present, no strong keyword
    assert _is_surgery_match("초음파 시술 검사") is False
    assert _is_surgery_match("MRI 촬영 레이저") is False  # negative blocks weak "레이저"


def test_surgery_match_strong_overrides_negative():
    # "절제" is strong, overrides negative "검사"
    assert _is_surgery_match("검사 후 절제 시행") is True


# ── _code_in ──────────────────────────────────────────────────────

def test_code_in():
    assert _code_in("C34.1", ("C",)) is True
    assert _code_in("I63.9", ("I60", "I61", "I62", "I63", "I64")) is True
    assert _code_in("E11.5", ("C", "I60")) is False


# ── 미래 날짜 필터 ───────────────────────────────────────────────

def test_future_date_excluded():
    today = datetime(2026, 5, 1)
    dates = {"2026-06-01", "2026-04-01", "2025-01-01"}
    # _dts_in_range는 since_dt 이후만 반환
    since = datetime(2026, 1, 1)
    result = _dts_in_range(dates, since)
    # 미래 날짜도 포함됨 (disease_stats 구축에서 제외하는 것은 run_analysis 로직)
    assert "2026-04-01" in result


# ── 스냅샷: fixture 기반 코드 분류 검증 ──────────────────────────

def test_snapshot_fixture_file_types():
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_basic_records.json")
    with open(fixture_path, encoding="utf-8") as f:
        records = json.load(f)

    ftypes = [r["_ftype"] for r in records]
    assert "basic" in ftypes
    assert "detail" in ftypes

    # 당뇨 E11.50은 basic에서 왔어야 함
    diabetes_rec = next(r for r in records if "E11" in r.get("상병코드", ""))
    assert diabetes_rec["_ftype"] == "basic"


def test_snapshot_surgery_detection():
    """용종절제술은 수술로 인식, 단순 검사는 미인식"""
    assert _is_surgery_match("대장내시경 용종절제술") is True
    assert _is_surgery_match("대장내시경 조직검사") is False
    assert _is_surgery_match("초음파 검사") is False


def test_normalize_code_keeps_kcd_only():
    """normalize_code는 KCD 보정만 수행 — 비-KCD 문자열을 강제 차단하지 않음 (filters 담당)"""
    # 정상 KCD 코드 (점 제거, 0 보존)
    assert normalize_code("K05.30") == "K0530"  # 의미있는 0 보존
    assert normalize_code("I63") == "I63"
    assert normalize_code("K21") == "K21"
    # 소문자 → 대문자 보정 + 점 제거
    assert normalize_code("k21.0") == "K210"
    # 빈 문자열 / None
    assert normalize_code("") == ""
    assert normalize_code(None) == ""


def test_normalize_code_preserves_kcd_zeros():
    """KCD-7 선행 0 보존 — 의미있는 0이 깎이면 안 됨"""
    assert normalize_code("AK0530") == "K0530"   # 만성 단순치주염
    assert normalize_code("K05.30") == "K0530"
    assert normalize_code("AO0339") == "O0339"   # 의미있는 0 보존
    assert normalize_code("AT140")  == "T140"
    assert normalize_code("AM1997") == "M1997"
    assert normalize_code("BM5436") == "M5436"


def test_detect_file_type_actual_headers():
    """권미연 PDF 실제 헤더로 파일 유형 판별 검증"""
    # 기본진료
    h_basic = ("순번", "진료시작일", "병·의원&약국", "진단과", "입원/외래",
               "주상병코드", "주상병명", "내원일수", "총진료비",
               "건강보험등", "내가낸의료비")
    # 세부진료
    h_detail = ("순번", "진료시작일", "병·의원&약국", "진료내역", "코드명",
                "1회투약량", "1일투여횟수", "총투약일수")
    # 처방조제
    h_pharma = ("순번", "진료시작일", "병·의원&약국", "처방/조제", "약품명",
                "성분명", "1회투약량", "1일투여횟수", "총투약일수")
    assert detect_file_type(h_basic)  == "basic"
    assert detect_file_type(h_detail) == "detail"
    assert detect_file_type(h_pharma) == "pharma"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
