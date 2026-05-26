"""Gemini AI 호출 일체 — analyzer.py 에서 이동."""
from __future__ import annotations

import asyncio
import json

from google import genai
from google.genai import types

from .helpers import AnalysisError, _worst_insurance_verdict, extract_json

# ── 의학 판단 전용 시스템 프롬프트 ──────────────────────────────
MEDICAL_JUDGMENT_SYSTEM_PROMPT = """당신은 한국 보험 언더라이팅 전문 의사입니다.
설계사가 고객의 알릴의무를 판단할 수 있도록 의학적 관점에서 분석합니다.

판단할 항목:
1. 추가검사/재검사 여부 (1년 이내 알릴의무 Q2)
2. 치료 종결 여부 (3개월 이내 알릴의무 Q1)

반드시 JSON 형식으로만 응답하세요.

[판단 1: 추가검사/재검사 여부]
판단 기준:
- 정기검사, 추적관찰, 건강검진, 모니터링, 단순 스케일링 → false
- 이상소견 후 정밀검사, 재검사, 추가 진단 목적 검사 → true
핵심: 질병코드와 검사 내용의 의학적 연관성 + 정기성 vs 재검사 구분
예) 치주염 정기 스케일링 = false / 종양 의심 후 조직검사 = true

[판단 2: 치료 종결 여부]
판단 기준:
- 일회성 감기, 단순 외상, 종결된 시술 → false (종결됨)
- 만성질환, 재발 가능성, 지속 투약 중 → true (진행 중)
- 수술 후 회복기, 처방약 복약 중 → true (진행 중)
- 처방 종료 후 추가 처방 없음 → false (종결됨)
핵심: 질병코드의 만성/급성 구분 + 마지막 처방 종료일 + 재방문 가능성"""


def _finalize_raw_text_for_gemini(
    filtered_lines: list[str],
    visit_count_lines: list[str],
    cross_surgery_hints: list[str],
    first_diag_lines: list[str],
    drug_change_text: str,
    presc_end_text: str,
) -> str:
    # 기존: filtered_lines[:800] — OOM 방지용 보수적 상한, 대용량 세부진료 PDF 잘림 발생
    raw_text = "\n".join(filtered_lines[:2000])
    if visit_count_lines:
        raw_text = "[10년내 질병코드별 통원횟수 집계 — Q4 7회이상통원 판단 기준]\n" \
                   + "\n".join(visit_count_lines) + "\n\n" + raw_text
    if cross_surgery_hints:
        raw_text = "[기본/세부 동일일자 교차검증 — 수술 추정 근거]\n" \
                   + "\n".join(f"- {h}" for h in cross_surgery_hints[:80]) + "\n\n" + raw_text
    if first_diag_lines:
        raw_text = "[질병별 최초·최종 진단일 — 고지사항 최초진단일 확인]\n" \
                   + "\n".join(first_diag_lines[:100]) + "\n\n" + raw_text
    if drug_change_text:
        raw_text = drug_change_text + "\n" + raw_text
    if presc_end_text:
        raw_text = presc_end_text + "\n" + raw_text
    # 기존: MAX_RAW_TEXT_LEN = 30_000
    MAX_RAW_TEXT_LEN = 80_000
    if len(raw_text) > MAX_RAW_TEXT_LEN:
        raw_text = raw_text[:MAX_RAW_TEXT_LEN] + "\n... (truncated)"
    return raw_text


def _merge_ai_results(parts: list[dict]) -> dict:
    if not parts:
        raise AnalysisError("AI 분석 결과가 없습니다.")
    merged: dict = {
        "flagged_items": [],
        "exempt_items": [],
        "drug_change_hit": False,
        "drug_change_reason": "",
        "total_flagged": 0,
    }
    hit_bool_keys = [
        "q1_hit", "q2_hit", "q3_hit", "q4_hit",
        "simple_q1_hit", "simple_q2_hit", "simple_q3_hit",
    ]
    reason_join_keys = [
        "q1_reason", "q2_reason", "q3_reason", "q4_reason",
        "simple_q1_reason", "simple_q2_reason",
    ]
    for p in parts:
        merged["flagged_items"].extend(p.get("flagged_items") or [])
        merged["exempt_items"].extend(p.get("exempt_items") or [])
        if p.get("drug_change_hit"):
            merged["drug_change_hit"] = True

    for k in hit_bool_keys:
        merged[k] = any(bool(x.get(k)) for x in parts)

    for k in reason_join_keys:
        texts = [x.get(k) for x in parts if x.get(k)]
        merged[k] = "; ".join(texts) if texts else ""

    dcr = [x.get("drug_change_reason") for x in parts if x.get("drug_change_reason")]
    merged["drug_change_reason"] = "; ".join(dcr) if dcr else ""

    sq3 = None
    for x in parts:
        v = x.get("simple_q3_disease")
        if v:
            sq3 = v
            break
    merged["simple_q3_disease"] = sq3

    merged["health_verdict"] = _worst_insurance_verdict(*(x.get("health_verdict") or "" for x in parts))
    hr = [x.get("health_reason") for x in parts if x.get("health_reason")]
    merged["health_reason"] = "; ".join(hr) if hr else ""

    merged["simple_verdict"] = _worst_insurance_verdict(*(x.get("simple_verdict") or "" for x in parts))
    sr = [x.get("simple_reason") for x in parts if x.get("simple_reason")]
    merged["simple_reason"] = "; ".join(sr) if sr else ""

    rec = [x.get("recommend") for x in parts if x.get("recommend")]
    merged["recommend"] = "; ".join(rec) if rec else ""

    summ = [x.get("summary") for x in parts if x.get("summary")]
    merged["summary"] = "\n".join(summ) if summ else ""

    merged["total_flagged"] = len(merged["flagged_items"])
    return merged


async def _call_medical_judgment(
    type1_items: list[dict],
    type2_items: list[dict],
    api_key: str,
) -> dict:
    """추가검사/재검사 + 치료 종결 여부를 단일 Gemini 배치 호출로 판단."""
    if not type1_items and not type2_items:
        return {"additional_tests": {}, "treatment_ongoing": {}}

    parts = []
    if type1_items:
        parts.append(
            "[추가검사/재검사 판단 목록]\n"
            + json.dumps(type1_items, ensure_ascii=False, indent=2)
        )
    if type2_items:
        parts.append(
            "[치료 종결 여부 판단 목록]\n"
            + json.dumps(type2_items, ensure_ascii=False, indent=2)
        )

    contents = "\n\n".join(parts) + """

[추가검사/재검사 판단 원칙]
- detail_test_events는 세부진료 행위 중 검사 후보만 기계적으로 추린 자료입니다. 이 목록이 있다고 해서 곧바로 추가검사/재검사 고지가 아닙니다.
- 같은 질병코드에서 최근 1년 이내 검사 후보가 2회 이상 또는 2종 이상인 경우만 후보로 전달됩니다.
- true 판단: 진찰/검사 후 이상소견 확인, 추적 관찰 중 재검, 추가 진단 목적 검사, 같은 질병에 대한 반복 확인 검사로 보이는 경우.
- false 판단: 초진 당일 한 번에 시행된 기본 검사 묶음, 건강검진/스크리닝/정기 모니터링, 단순 처방·처치 전 확인검사, 검사 후 추가 검사 없이 치료만 이어진 경우.
- same_day_detail_actions를 함께 보고 진찰/처방/처치와 검사 후보가 어떤 관계인지 판단하세요.

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON:
{
  "additional_tests": [
    {"disease_code": "코드", "is_additional_test": true또는false, "test_type": "재검사 또는 정기검사", "reason": "판단 근거"}
  ],
  "treatment_ongoing": [
    {"disease_code": "코드", "is_ongoing": true또는false, "reason": "판단 근거"}
  ]
}"""

    try:
        api_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=120_000),
        )
    except TypeError:
        api_client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        system_instruction=MEDICAL_JUDGMENT_SYSTEM_PROMPT,
        temperature=0,
    )

    def _sync_gen():
        return api_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=config,
        )

    try:
        if hasattr(api_client, "aio") and hasattr(api_client.aio.models, "generate_content"):
            message = await api_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=config,
            )
        else:
            message = await asyncio.to_thread(_sync_gen)

        raw = message.text if getattr(message, "text", None) else ""
        if not raw.strip():
            return {"additional_tests": {}, "treatment_ongoing": {}}

        result = extract_json(raw)
        at_out = {
            item["disease_code"]: item
            for item in result.get("additional_tests", [])
            if isinstance(item, dict) and "disease_code" in item
        }
        to_out = {
            item["disease_code"]: item
            for item in result.get("treatment_ongoing", [])
            if isinstance(item, dict) and "disease_code" in item
        }
        return {"additional_tests": at_out, "treatment_ongoing": to_out}
    except Exception as e:
        return {"additional_tests": {}, "treatment_ongoing": {}, "_error": str(e)[:120]}


async def analyze_single_pdf(parsed_data: dict, product_type: str, reference_date, api_key: str) -> dict:
    """파싱된 PDF 1건에 대해 Gemini 분석 (비동기)."""
    _ = reference_date
    fname = parsed_data["filename"]
    today_str = parsed_data["today_str"]
    raw_text = parsed_data["raw_text"]
    pdf_bytes = parsed_data.get("pdf_bytes")  # SURIT-007: PDF 네이티브 첨부용
    system_prompt = parsed_data["system_prompt"]
    retry_local: list[str] = []

    GEMINI_TIMEOUT_SECONDS = 240
    try:
        api_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
        )
    except TypeError:
        api_client = genai.Client(api_key=api_key)

    ai_result = None
    last_error = None
    raw_response = ""
    MAX_RETRIES = 5
    RETRY_DELAYS = [5, 10, 20, 40, 60]
    # SURIT-007: PDF 바이너리가 있으면 Gemini 네이티브 첨부 — 잘림 없이 전체 PDF 전달.
    # 보조 가공 데이터(통원집계·태깅·약변경)는 텍스트로 함께 동봉한다.
    if pdf_bytes:
        instruction = (
            f"고객 기준일: {today_str}\n심사 유형: {product_type}\n\n"
            f"첨부된 PDF는 심평원에서 발급한 진료 데이터입니다. "
            f"시스템 프롬프트의 규칙에 따라 알릴의무 항목을 정확히 판단하세요.\n\n"
            f"[보조 분석 자료 — 사전 가공된 통원/처방/태그 데이터]\n{raw_text}"
        )
        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        # SURIT-007 fix: SDK 2.6.0 에서 contents=[Part, str] 혼합은 inline_data Part 와
        # 함께 있을 때 HTTP 400 (Invalid argument) 을 유발한다. 텍스트도 명시적 Part 로
        # 감싸 모든 원소를 Part 로 통일한다 (Railway 400 핫픽스).
        contents = [pdf_part, types.Part.from_text(text=instruction)]
    else:
        # 텍스트 fallback (PDF 파싱 실패 등)
        contents = f"고객 기준일: {today_str}\n심사 유형: {product_type}\n\n진료 데이터:\n{raw_text}"
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0,
    )

    def _sync_generate():
        return api_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=config,
        )

    for attempt in range(MAX_RETRIES):
        try:
            if hasattr(api_client, "aio") and hasattr(api_client.aio.models, "generate_content"):
                message = await api_client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=config,
                )
            else:
                message = await asyncio.to_thread(_sync_generate)
            raw_response = message.text if getattr(message, "text", None) else ""
            if not raw_response.strip():
                raise ValueError("AI 응답이 비어있습니다.")
            ai_result = extract_json(raw_response)
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                continue
            return {
                "filename": fname,
                "ai_result": None,
                "retry_warnings": retry_local,
                "error": f"AI 응답 파싱 오류: {e}",
                "raw_response_snip": raw_response[:800],
            }
        except Exception as e:
            err_str = str(e)
            _retryable = ("503", "UNAVAILABLE", "high demand", "overloaded",
                          "429", "RESOURCE_EXHAUSTED", "rate limit", "quota")
            if any(s in err_str for s in _retryable) and attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAYS[attempt]
                retry_local.append(
                    f"[{fname}] Gemini 호출이 지연되어 {wait}초 후 재시도합니다... ({attempt + 1}/{MAX_RETRIES - 1})"
                )
                await asyncio.sleep(wait)
                continue
            return {"filename": fname, "ai_result": None, "retry_warnings": retry_local, "error": str(e)}

    if ai_result is None:
        return {
            "filename": fname,
            "ai_result": None,
            "retry_warnings": retry_local,
            "error": str(last_error),
            "raw_response_snip": raw_response[:800] if raw_response else "",
        }

    return {"filename": fname, "ai_result": ai_result, "retry_warnings": retry_local, "error": None}
