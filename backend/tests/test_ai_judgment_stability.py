"""SURIT-VERIFY-001: AI 판단 호출 파라미터 안정화 회귀 테스트.

실제 Gemini 호출은 하지 않고(샌드박스에서 API 키·네트워크 불가),
ai_judgment.py 내부에서 GenerateContentConfig 가 결정성 보조 파라미터
(temperature=0, top_k=1, top_p=1.0, seed=42, response_mime_type) 를
설정하도록 코드 자체가 변경됐는지 정적으로 검증한다.

목적:
- 동일 입력으로 다시 호출했을 때 출력이 흔들리지 않도록 결정성을 보장하는
  설정이 코드에서 빠지지 않게 회귀 잠금.
- 시스템 프롬프트에서 "추측"·"가능성"·"~일 수 있다" 같은 주관적 표현을
  추가로 도입하는 것을 차단.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pipeline.ai_judgment as aij


def _ai_judgment_source() -> str:
    with open(aij.__file__, "r", encoding="utf-8") as f:
        return f.read()


def test_gemini_config_sets_temperature_zero():
    """temperature=0 이 양쪽 Gemini 호출 config 에 명시돼야 한다."""
    src = _ai_judgment_source()
    # 의학 판단 호출 + analyze_single_pdf 호출 = 2 회 이상 등장 보장
    assert src.count("temperature=0") >= 2, (
        "temperature=0 설정이 양쪽 Gemini 호출에 있어야 한다 — 결정성 보장"
    )


def test_gemini_config_sets_top_k_and_seed():
    """top_k=1, seed=42, top_p=1.0 결정성 보조 파라미터가 있어야 한다."""
    src = _ai_judgment_source()
    # top_k=1 / seed=42 / top_p=1.0 / response_mime_type 모두 2회 이상 등장
    for needle in ("top_k=1", "seed=42", "top_p=1.0", 'response_mime_type="application/json"'):
        assert src.count(needle) >= 2, f"{needle} 가 양쪽 호출 config 에 모두 있어야 한다"


def test_medical_judgment_prompt_no_speculation():
    """의학 판단 시스템 프롬프트에 추측·확률 표현이 남아 있지 않아야 한다."""
    prompt = aij.MEDICAL_JUDGMENT_SYSTEM_PROMPT
    forbidden = ["일 수 있다", "재발 가능성", "재방문 가능성"]
    for token in forbidden:
        assert token not in prompt, f"프롬프트에 모호한 표현 '{token}' 이 남아있다"


def test_medical_judgment_prompt_has_deterministic_guard():
    """프롬프트에 동일 입력→동일 출력 강제 규칙이 명시돼야 한다."""
    prompt = aij.MEDICAL_JUDGMENT_SYSTEM_PROMPT
    assert "동일한 입력 데이터에 대해 동일한 출력" in prompt, (
        "결정성 가드 문구가 빠졌다 — 향후 추측 표현 재도입 위험"
    )


def test_typeerror_fallback_preserves_temperature():
    """SDK 미지원 파라미터로 TypeError 시 fallback config 도 temperature=0 을 유지한다."""
    src = _ai_judgment_source()
    # except TypeError 블록 안에서 temperature=0 명시가 양쪽 모두 보장
    assert src.count("except TypeError:") >= 2
    assert src.count("temperature=0") >= 4, (
        "fallback config 포함 temperature=0 가 4회 이상 등장해야 한다 "
        "(메인 + fallback × 의학 + analyze)"
    )
