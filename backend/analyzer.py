"""SURIT 분석 엔진 — 오케스트레이터.
실제 로직은 backend/pipeline/* 에 분산되어 있다.

이 파일은 run_analysis() 오케스트레이션 + 하위 호환 re-export 를 담당한다.
"""
import asyncio
import gc
import re
from datetime import datetime, timedelta

from filters import build_code_based_items as _build_code_based_items
# SURIT-BUG-008: meritz_easy_rules.evaluate_meritz_easy 제거.

# ── pipeline re-export (테스트·외부 임포트 호환) ─────────────────
from pipeline.helpers import (
    AnalysisError,
    _clean_disease_name,
    _code_in,
    _dts_in_range,
    _inpatient_periods_in_range,
    _max_presc,
    _parse_ymd,
    _recent_detail_test_events,
    _detail_test_type_count,
    _sorted_strings,
    _visit_count_in_range,
    extract_drug_info,
    extract_json,
    format_kcd_code,
    get_diagnosis_code,
    get_diagnosis_name,
    get_val,
    normalize_code,
    parse_date,
    row_is_junk,
    _is_surgery_match,
    _subtract_years,
    HEALTH_Q5_CODES,
)
from pipeline.pdf_parser import detect_file_type, parse_single_pdf
from pipeline.disease_aggregator import (
    new_disease,
    build_disease_stats,
    detect_drug_changes,
    compute_prescription_end_dates,
)
from pipeline.ai_judgment import (
    MEDICAL_JUDGMENT_SYSTEM_PROMPT,
    _call_medical_judgment,
    _finalize_raw_text_for_gemini,
    _merge_ai_results,
    analyze_single_pdf,
)
from pipeline.result_builder import (
    _build_reports_for_product,
    _build_all_disease_summary,
    _make_merged_item,
    build_summary_reports,
)


# ── SURIT-003: 초대용량 PDF AI 입력 잘림 감지 ───────────────────────
# ai_judgment._finalize_raw_text_for_gemini 가 cleaned_lines[:13_000] 로 줄을
# 자르고, 길이가 300,000자를 넘으면 "... (truncated)" 표식을 붙인다. 잘림
# 로직 자체는 변경하지 않고, analyzer 호출부에서 잘림 여부만 감지한다.
# SURIT-ROLLBACK-001: 2000 → 3000 으로 상향. SURIT-BUG-009: 3000 → 13_000 으로 추가 상향
# (BUG-008 메리츠 간편 제거로 Gemini 호출 단일화 + 300초 타임아웃 여유 — 318p 전체 커버).
_GEMINI_LINE_CAP = 13_000  # ai_judgment 슬라이스와 동기 (기존: 800 → 2000 → 3000 → 13_000 / MAX_RAW_TEXT_LEN 30_000 → 80_000 → 100_000 → 300_000)


def _is_gemini_input_truncated(file_lines: list, raw_text: str) -> bool:
    """해당 PDF의 진료 내역이 AI 입력 한도(줄/글자 수)에 걸려 잘렸는지 판정.

    줄 잘림은 filtered_lines 길이가 _GEMINI_LINE_CAP 초과인지로, 글자 잘림은
    완성된 raw_text 끝의 "... (truncated)" 표식 유무로 감지한다.
    """
    return len(file_lines) > _GEMINI_LINE_CAP or raw_text.endswith("... (truncated)")


def _build_truncation_warning(truncated_files: list) -> str | None:
    """잘림이 발생한 PDF가 있으면 사용자 경고 문구를, 없으면 None을 반환한다."""
    if not truncated_files:
        return None
    return (
        "⚠️ PDF 용량이 커서 일부 진료 내역이 AI 분석 입력에서 제외됐을 수 있습니다. "
        "분석 결과가 불완전할 수 있으니 진료 원자료로 직접 확인해 주세요. "
        f"(해당 파일: {', '.join(truncated_files)})"
    )


async def _parse_all_pdfs(active_files: list, birthdate_pw: str) -> tuple[list, list]:
    """PDF들을 순차 파싱해 (레코드, 파싱오류) 반환. 레코드 0건이면 AnalysisError.

    OOM 핫픽스: 여러 PDF를 동시 파싱하면 pdfplumber 페이지 캐시가 파일 수만큼
    메모리에 동시에 쌓여 Railway 컨테이너 메모리 한도를 초과, 프로세스가 강제
    종료됐다 (files=2 에서 재현). 파일을 한 개씩 순차 처리해 메모리 피크를
    PDF 1개분으로 제한한다. parse_single_pdf 는 finally 에서 자체 gc 하므로
    다음 파일 파싱 전에 직전 파일의 메모리가 해제된다.
    """
    all_records = []
    parse_errors = []
    # ── PDF 파싱 (순차 처리 — 메모리 피크 억제) ──
    for i, uf in enumerate(active_files):
        fn = getattr(uf, "name", None) or getattr(uf, "filename", None) or f"file_{i}"
        try:
            pr = await asyncio.to_thread(parse_single_pdf, uf, birthdate_pw)
        except Exception as e:
            parse_errors.append(f"⚠️ {fn}: PDF 파싱 중 예외 — {str(e)[:120]}")
            continue
        all_records.extend(pr["records"])
        parse_errors.extend(pr["parse_errors"])

    if not all_records:
        if parse_errors:
            raise AnalysisError(
                "PDF에서 진료 데이터를 추출하지 못했습니다.\n" + "\n".join(parse_errors)
            )
        raise AnalysisError(
            "PDF에서 진료 데이터를 추출하지 못했습니다. "
            "심평원에서 발급한 진료내역 PDF가 맞는지 확인해 주세요."
        )

    return all_records, parse_errors


def _build_drug_change_text(drug_change_summary: list[dict]) -> str:
    """약 변경 감지 결과를 Gemini 입력용 텍스트 블록으로 구성."""
    drug_change_text = ""
    if drug_change_summary:
        drug_change_text = "\n[처방약 변경 감지 결과 — 간편심사 Q1 판단 필수 참고]\n"
        for dc in drug_change_summary:
            drug_change_text += (
                f"- 질환: {dc['name']} / 변경유형: {dc['change_type']}\n"
                f"  · 3개월 이전 약(중단): {', '.join(dc['stopped']) if dc['stopped'] else '없음'}\n"
                f"  · 3개월 이내 신규약(추가/변경): {', '.join(dc['new']) if dc['new'] else '없음'}\n"
                f"  · 용량 증가 약(가입불가): {', '.join(dc['dose_increased']) if dc['dose_increased'] else '없음'}\n"
                f"  · 용량 감소 약(가입가능): {', '.join(dc['dose_decreased']) if dc['dose_decreased'] else '없음'}\n"
                f"  · 계속 유지 중인 약: {', '.join(dc['continued']) if dc['continued'] else '없음'}\n"
            )
        drug_change_text += (
            "※ 가입 불가: 약 종류 변경 / 새 약 추가 / 용량 증가\n"
            "※ 가입 가능: 동일 약 지속 복용(변경 없음) / 용량 감소 / 약 중단\n"
        )

    return drug_change_text


def _build_presc_end_text(
    prescription_end_details: list[dict],
    earliest_available_date: datetime | None,
    today: datetime,
) -> str:
    """처방 종료일 분석을 Gemini 입력용 텍스트 블록으로 구성."""
    presc_end_text = ""
    if prescription_end_details:
        presc_end_text = "\n[3개월 이내 처방 종료일 분석 — 가입 가능 날짜 계산]\n"
        for p in prescription_end_details:
            status = "✅ 이미 복약 완료 (가입 가능)" if p["already_ok"] else f"❌ 복약 중 (가입불가 ~ {p['end_date']})"
            presc_end_text += (
                f"- 질환: {p['name']}\n"
                f"  처방일: {p['presc_date']} / 투약일수: {p['m_days']}일 / 종료일: {p['end_date']}\n"
                f"  → 가입 가능 날짜: {p['available']} / 상태: {status}\n"
            )
        if earliest_available_date and earliest_available_date > today:
            presc_end_text += (
                f"\n★ 전체 처방 기준 최소 가입 가능 날짜: {earliest_available_date.strftime('%Y-%m-%d')}\n"
                f"  (이 날짜 이전에 청약하면 3개월 이내 투약으로 Q1 해당)\n"
            )
        elif earliest_available_date and earliest_available_date <= today:
            presc_end_text += "\n★ 3개월 이내 처방이 있으나 모두 복약 완료 상태 — 투약 관련 Q1은 면제 가능\n"

    return presc_end_text


def _build_tagged_entries(
    raw_entries: list[tuple[str, str]],
    today: datetime,
    _d5y_dt: datetime,
    _d10y_dt: datetime,
) -> dict[str, list[str]]:
    """진료 라인에 기간 태그(IN_3M 등)를 붙여 파일별로 묶어 반환."""
    # ── 날짜 태그 필터링 ─────────────────────────────────────────
    filtered_entries = []
    for fname_row, line in raw_entries:
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
        if not date_match:
            filtered_entries.append((fname_row, line))
            continue
        line_date = date_match.group(1)
        try:
            dt = datetime.strptime(line_date, "%Y-%m-%d")
        except ValueError:
            filtered_entries.append((fname_row, line))
            continue
        days_ago = (today - dt).days
        # SURIT-004: 5년/10년 경계는 윤년 보정 위해 달력 기준 컷오프와 비교한다.
        # 3개월/1년은 윤년 영향이 없어 일수(days_ago) 비교를 유지한다.
        if days_ago < 0 or dt < _d10y_dt:
            continue
        tags = []
        if days_ago <= 90:   tags.append("IN_3M")
        if days_ago <= 365:  tags.append("IN_1Y")
        if dt >= _d5y_dt:    tags.append("IN_5Y")
        if dt >= _d10y_dt:   tags.append("IN_10Y")
        filtered_entries.append((fname_row, line + " [" + ",".join(tags) + "]"))

    filtered_lines = [t[1] for t in filtered_entries]
    from collections import defaultdict as _dd
    lines_by_file_tagged = _dd(list)
    for fname_row, tl in filtered_entries:
        if fname_row:
            lines_by_file_tagged[fname_row].append(tl)

    return lines_by_file_tagged


def _build_visit_count_lines(disease_stats: dict, _d10y_dt: datetime) -> list[str]:
    """질병코드별 10년내 통원횟수·최대처방일 집계 라인 구성."""
    # ── 통원횟수·처방일수 집계 ───────────────────────────────────
    visit_count_lines = []
    for _code, _s in disease_stats.items():
        _visits_in_10y = []
        for _d in _s["visit_dates"]:
            try:
                if datetime.strptime(_d, "%Y-%m-%d") >= _d10y_dt:
                    _visits_in_10y.append(_d)
            except ValueError:
                pass
        _med_dict = _s["med_dates_pharma"] if _s.get("has_pharma") and _s["med_dates_pharma"] else _s["med_dates_basic"]
        _max_presc_days = 0
        for _pd, _pv in _med_dict.items():
            try:
                if datetime.strptime(_pd, "%Y-%m-%d") >= _d10y_dt:
                    if _pv > _max_presc_days:
                        _max_presc_days = _pv
            except ValueError:
                pass
        _name = _s.get("name", "")[:15]
        if _visits_in_10y:
            _cnt   = len(_visits_in_10y)
            _first = min(_visits_in_10y) if _visits_in_10y else "-"
            _last  = max(_visits_in_10y) if _visits_in_10y else "-"
            _presc_note = f" 최대처방{_max_presc_days}일" if _max_presc_days > 0 else ""
            _7day_flag = " ★7회이상" if _cnt >= 7 else ""
            visit_count_lines.append(
                f"[통원집계] {_code} {_name} 10년내통원{_cnt}회 ({_first}~{_last}){_presc_note}{_7day_flag}"
            )

    return visit_count_lines


def _build_first_diag_lines(disease_stats: dict) -> list[str]:
    """질병별 최초·최종 진단일 라인 구성."""
    # ── 최초 진단일 ───────────────────────────────────────────────
    first_diag_lines = []
    for _ck, _s in disease_stats.items():
        _fd = _s.get("first_date", "2099-12-31")
        if _fd and _fd != "2099-12-31":
            _dc = _s.get("diag_code") or _ck
            _nm = _s.get("name", "")[:20]
            first_diag_lines.append(f"  {_dc} {_nm} 최초={_fd} 최종={_s.get('latest_date','')}")

    return first_diag_lines


def _build_system_prompt(
    product_type: str,
    today_str: str,
    d_3m: str,
    d_1y: str,
    d_5y: str,
    d_10y: str,
) -> str:
    """상품유형별 Gemini 시스템 프롬프트 전문을 구성."""
    # ── 시스템 프롬프트 구성 ─────────────────────────────────────
    # SURIT-BUG-008: 간편심사 제거 — 건강체 분기만 유지.
    is_health = True
    _ = product_type  # 시그니처 호환 유지
    step2_tag_rules = (
        "건강체/표준체 기준:\n"
        "- [IN_3M] 있어야만 → Q1 배정 가능\n"
        "- [IN_1Y] 있어야만 → Q2 배정 가능\n"
        "- [IN_10Y] 있어야만 → Q3 배정 가능\n"
        "- [IN_5Y] 있어야만 → Q4 배정 가능\n"
        "- [IN_3M] 없으면 → Q1 배정 절대 불가\n"
        "- [IN_10Y]만 있고 [IN_3M] 없으면 → Q3만 배정 (Q1 절대 불가)\n"
        "★ 사용 가능한 질문번호: Q1, Q2, Q3, Q4 뿐. Q5는 절대 사용 금지.\n"
        "  Q1=3개월(진단·투약·특정약물), Q2=1년(추가검사), Q3=10년(입원/수술/7회이상/30일이상), Q4=5년(중대질병)"
    )

    if is_health:
        criteria_text = f"""
[건강체/표준체 알릴의무 4문항] (기준일: {today_str})
Q1. 최근 3개월({d_3m} 이후) — 태그 [IN_3M] 항목만: 아래 중 하나라도 해당 시 고지
    ① 질병확정진단 / 의심소견 / 추가검사 필요소견
    ② 입원
    ③ 수술 (제왕절개 포함)
    ④ 투약 (의사 처방만, 약국 자가구매 제외)
    ⑤ 마약·혈압강하제·신경안정제·수면제·각성제·흥분제·진통제 상시 복용
Q2. 최근 1년({d_1y} 이후) — 태그 [IN_1Y] 항목만: 의사 진찰·검사 후 추가검사(재검사) 받은 사실
    ★ Q2 추가검사(재검사) 정확한 정의:
       [해당 O] 진찰 결과 이상소견이 확인되어 더 정확한 진단을 위해 시행한 추가 검사
               예) X-RAY 촬영 후 이상소견 → MRI·CT·혈액검사 등 추가 시행
       [해당 X — 반드시 Q2 면제] 아래 경우는 절대 Q2 배정 불가:
               - 정기검사·추적관찰 (치료 없이 유지 상태에서 주기적으로 시행)
               - 단순 1회 검사만 시행하고 종결 (이상소견 없는 경우)
               - 검사 후 추가 검사 없이 단순 치료로만 이어진 경우 → Q2 아닌 Q1/Q3로 판단
Q3. 최근 10년({d_10y} 이후) — 태그 [IN_10Y] 항목만: 아래 중 하나라도 해당 시 고지
    - 입원
    - 수술 (제왕절개 포함)
    - 동일질병 계속하여 7일 이상 치료 ★ = 동일 KCD코드 기준 통원횟수 7회 이상
    - 동일질병 계속하여 30일 이상 투약 (단일 처방 30일 이상 OR 만성질환 매월 지속 처방)
Q4. 최근 5년({d_5y} 이후) — 태그 [IN_5Y] 항목만: 아래 중대질병 확정진단만 해당
    ① 암 (악성신생물): C00~C97, D00~D09
    ② 백혈병: C91~C95 (암 포함)
    ③ 고혈압: I10~I15
    ④ 협심증: I20
    ⑤ 심근경색: I21~I22
    ⑥ 심장판막증: I05~I09, I34~I38
    ⑦ 간경화증: K74
    ⑧ 뇌출혈: I60~I62
    ⑨ 뇌경색: I63~I64
    ⑩ 당뇨병: E10~E14
    ⑪ 에이즈: B20~B24
    ★ Q4 면제: 위 코드 범위에 해당하지 않는 모든 질환 → Q4 배정 불가"""
        step4_surgery_text = """
━━━━━━━━━━━━━━━━━━━━━━━━━━
[4단계: Q3 수술 인정 목록 — 반드시 is_surgery=true]
━━━━━━━━━━━━━━━━━━━━━━━━━━

[소화기 내시경 수술]
- K63.5/AK635 결장용종 → 대장내시경 용종절제술 ★반드시 수술
- K31/AK31 위용종 → 위내시경 용종절제술
- K92.1 혈변+내시경 지혈술 → 수술
- 위/대장 폴립, 용종 관련 진료비 30만원 이상 외래 → 수술 가능성

[치과 수술]
- K08.1/AK081 발치 → 발치술 ★반드시 수술
- K04.7/AK047 근단주위농양 절개 → 수술
- 임플란트 시술 → 수술

[안과 수술]
- H25/AH25 백내장 → 백내장 수술 (진료비 50만원 이상)
- H33/AH33 망막박리 → 망막수술
- H40/AH40 녹내장 수술

[정형/신경외과 수술]
- 척추/관절 진료비 50만원 이상 + 입원 → 수술 가능
- 골절(S계열) + 수술 키워드 → 골절 수술

[산부인과 수술]
- O84/AO84 제왕절개 → ★반드시 수술
- D25/AD25 자궁근종 절제 → 수술
- N83/AN83 난소낭종 제거 → 수술

[피부/성형외과 수술]
- L02/AL02 농양 절개배농 → 수술
- M72.66/AM7266 괴사성근막염 → 광범위절제술 ★반드시 수술 (critical)
- L84/AL84 티눈·굳은살 → 행위명에 제거술·소작·레이저·냉동 포함 시 ★반드시 수술
- 행위명에 "제거술","소작술","냉동치료","레이저절제","배농술","절개배농" 포함 → 수술
- 피부과 진료비 10만원 이상 + 절개·제거·소작 키워드 → 수술

[공통 수술 판단 규칙]
- 입원 동반 + 외과/흉부외과/성형외과/산부인과 → 수술 가능성 높음
- 진료비 총액 100만원 이상 외래 1회 → 수술 강력 의심
- 병명/진료내역에 절제·절개·봉합·이식·성형·제거·적출 포함 → 수술"""
        step5_q4_exempt_text = """
▶ Q3 반드시 면제 처리 항목:
  ① 동일 질병코드 통원횟수 6회 이하 (7회 미만), 투약 30일 미만, 입원 없음, 수술 없음
     ★ "계속하여 7일 이상 치료"는 처방일수가 아닌 통원횟수 기준 — [통원집계]에서 해당 코드 통원횟수가 7회 미만이면 반드시 면제
     ★★ 처방일수 7일 이상이라도 통원횟수 7회 미만이면 "7일 이상 치료" 해당 아님
     ★★★ 이 규칙은 정신건강의학과(F계열)·신경과 포함 모든 진료과에 동일하게 적용
        정신건강의학과 1회 방문 + 투약 30일 미만 → Q3 절대 면제 (weight=high여도 면제)
  ② 단순 감기·비염·인후염·결막염·두드러기·타박상·염좌 (통원횟수 무관하게 Q3 면제)
  ③ 치과 스케일링·단순 충치 보존치료 (발치·임플란트 제외)
  ④ 한방 단순 침구치료 (수술/입원 미동반)
  ⑤ 단순 통원 검사만 받고 종결 (수술/입원/통원7회이상 치료 없음)
  ⑥ 방광염·요로감염 단순 항생제 투약 (1회성)
  ⑦ 알레르기성 피부염 단순 외래 1~2회
  ⑧ 정신건강의학과·신경과·심리검사 단순 1회 방문 (통원 7회 미만, 입원 없음, 투약 30일 미만) → Q3 면제

★★ 질병코드 원칙: 질병코드(KCD)는 반드시 기본진료에서 확인된 코드만 사용.
   처방조제(약품명)로부터 질병코드를 추정/예측하지 마세요.
   처방조제 데이터는 투약일수·약 변경 판단에만 사용합니다.

▶ 만성질환 30일이상 투약 판단:
  - 당뇨(E11계열): 매월 지속 처방 확인 시 → med_days=365, Q3 해당 (Q2 아님)
  - 고혈압(I10계열): 매월 지속 처방 → med_days=365, Q3 해당 (Q2 아님)
  - 고지혈증(E78계열): 매월 지속 처방 → med_days=365, Q3 해당
  - 갑상선(E03/E05): 매월 지속 처방 → med_days=365, Q3 해당
  - 단, 3개월 이내에만 처방 기록이 있고 이전 기록 없음 → Q1 해당 가능"""
        json_duty_q_values = "Q1 또는 Q2 또는 Q3 또는 Q4 (Q5는 절대 사용 금지)"
        json_hit_fields = """\
  "q1_hit": true또는false, "q1_reason": "진단/입원/수술/투약/특정약물상시복용 중 해당 사유",
  "q2_hit": true또는false, "q2_reason": "추가검사(재검사) 사유 또는 없음",
  "q3_hit": true또는false, "q3_reason": "입원/수술/7회이상통원/30일이상투약 중 해당 사유",
  "q4_hit": true또는false, "q4_reason": "중대질병명 및 KCD코드 또는 없음","""
        step5_q3_health_text = (
            "\n▶ 건강체 Q2 추가검사(재검사) 판단 기준 (★핵심 규칙):\n"
            "  Q2는 '진찰 후 이상소견 → 추가 검사' 두 단계가 반드시 존재해야 함.\n\n"
            "  [Q2 해당 O — 반드시 포함]:\n"
            "  - 진찰 결과 이상소견 발견 → 더 정확한 진단을 위해 추가 검사 시행\n"
            "  - 예: 진찰 후 X-RAY → 이상소견 → MRI/CT/혈액검사/초음파 등 추가 시행\n"
            "  - 추가 검사는 당일이 아니어도 됨 (동일 질병코드로 연결된 경우)\n"
            "  - 검사 결과 이후 치료로 이어졌어도, 이상소견으로 추가 검사를 받은 사실 자체가 Q2\n\n"
            "  [Q2 해당 X — 반드시 면제]:\n"
            "  - 단순 1회 검사만 시행하고 종결 (X-RAY 1회, 혈액검사 1회, 초음파 1회 등 단독)\n"
            "  - 이상소견 없이 단순 확인·스크리닝 목적의 1회 검사\n"
            "  - 정기검사·추적관찰 (치료 없이 병증이 유지되는 상태에서 시행하는 주기적 검사)\n"
            "  - 검사 1종만 찍고 추가 검사 없이 바로 치료로 이어진 경우 → Q1 또는 Q3로만 처리\n"
            "  - 건강검진 항목으로 시행된 검사"
        )
        q3_diabetes_note = "(Q3만)"

    system_prompt = f"""당신은 보험 언더라이팅 전문 AI입니다.
건강보험심사평가원(건강e음) 진료 데이터를 분석하여 보험 청약 시 알릴의무(고지의무) 해당 항목을 정확히 판단합니다.
판단의 정확도가 최우선입니다. 과잉 고지도, 누락도 모두 금물입니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━
[0단계: 데이터 파일 구조 및 교차검증 원칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━
진료 데이터는 3개 파일에서 추출됩니다:
1) 기본진료정보: 입원/외래 구분, 주상병코드, 진료시작일, 총진료비
2) 세부진료정보(진료내역): 처치및수술 분류, 행위명, 급여비용
3) 처방진료정보: 약품명, 투약일수, 처방일

★★★ 질병코드(KCD) 원칙:
- 질병코드는 반드시 기본진료에 기록된 코드만 사용하세요.
- 처방조제(약품명)로부터 질병코드를 추정·예측하지 마세요.
- 처방조제 데이터는 투약일수·약 변경 판단에만 사용합니다.
- 최초 진단일~마지막 치료일은 병원에 관계없이 동일 질병코드 기준으로 판단하세요.

★ 교차검증 규칙 (동일 날짜 기록은 반드시 함께 확인):
- 세부진료 "처치및수술" 항목 + 기본진료 고비용(30만↑) → 수술 확정
- "[기본/세부 동일일자 교차검증]"에 "교차확정" 표기된 항목은 is_surgery=true 필수
- "교차후보 ★AI판단필요" 표기된 항목은 행위명/비용/입원여부를 종합 판단하세요

★ 최초 진단일 활용:
- "[질병별 최초·최종 진단일]"에서 동일 코드의 최초 진단일을 확인하세요
- 고지사항 date 필드에는 해당 질병의 최초 진단일을 기입하세요

━━━━━━━━━━━━━━━━━━━━━━━━━━
[1단계: 코드 전처리]
━━━━━━━━━━━━━━━━━━━━━━━━━━
- 코드 앞 A(양방)/B(한방) 접두사 제거 (예: AK635→K63.5, AE1150→E11.50, BM179→M17.9)
- 숫자 1로 시작하는 코드 → I로 교정 (OCR 오류, 예: 1670→I67.0)
- $ 또는 해당없음 행 → 완전 제외
- COVID 검사(AZ115/AU071/AU072) · 예방접종(AZ코드) → 완전 제외

━━━━━━━━━━━━━━━━━━━━━━━━━━
[2단계: 날짜 태그 기반 질문 배정 — 절대 규칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━
각 진료 데이터 끝에 붙은 태그만으로 해당 질문을 결정합니다.
태그에 없는 기간의 질문에는 절대 배정하지 마세요.
{step2_tag_rules}

{criteria_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[3단계: 간편심사 약 변경 판단 — 핵심 규칙]
━━━━━━━━━━━━━━━━━━━━━━━━━━
상단에 [처방약 변경 감지 결과]가 있으면 반드시 아래 기준으로 판단하세요.

▶ 간편심사 Q1 해당 (가입 불가):
  - 3개월 이전부터 복용하던 약의 종류가 변경된 경우
  - 3개월 이전에 없던 새로운 약이 3개월 이내 추가된 경우
  - 동일 약의 용량이 증가한 경우 (예: 500mg → 1000mg) ← 악화 신호
  → duty_question="Q1", reason에 구체적 변경 내용 명시

▶ 간편심사 Q1 해당 아님 (가입 가능):
  - 3개월 이전부터 동일 약을 변경 없이 계속 복용 중인 경우
  - 동일 약의 용량만 감소한 경우 (예: 1000mg → 500mg) ← 호전 신호
  - 복용하던 약이 중단된 경우 ← 호전 신호

━━━━━━━━━━━━━━━━━━━━━━━━━━
[3-1단계: 처방 종료일 기준 가입 가능 날짜 판단]
━━━━━━━━━━━━━━━━━━━━━━━━━━
상단에 [3개월 이내 처방 종료일 분석]이 있으면 반드시 아래 기준으로 판단하세요.

▶ 처방 종료일 계산 원칙:
  - 처방일 + 투약일수 = 처방 종료일 (마지막 복약일)
  - 처방 종료일 다음날 = 가입 가능 최소 날짜
  - 예: 3월 1일 처방 + 7일치 → 종료일 3월 7일 → 가입가능 3월 8일부터

▶ 3개월 이내 처방이 있는 경우 Q1 판단:
  - 복약 중(오늘 < 가입가능날짜): Q1 해당 → 가입불가, reason에 "복약 중 (가입가능날짜: YYYY-MM-DD)" 명시
  - 복약 완료(오늘 >= 가입가능날짜): Q1 해당 아님 → 투약 자체는 면제 가능
    단, 진단/소견 자체가 3개월 이내이면 Q1 해당 여부 별도 판단 필요

▶ 분석 데이터에서 "✅ 이미 복약 완료" 표시된 항목:
  - 해당 처방으로 인한 투약 Q1은 면제. 단 진단 자체가 3개월 이내면 Q1 해당 가능

▶ 분석 데이터에서 "❌ 복약 중" 표시된 항목:
  - 반드시 Q1 포함, reason에 "복약 중 — 가입 가능 날짜: [날짜]" 명시

{step4_surgery_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[5단계: 추가검사(Q2) 판단 + 면제 — 과잉 고지 방지]
━━━━━━━━━━━━━━━━━━━━━━━━━━
{step5_q3_health_text}

▶ 간편심사 Q3 절대 면제 규칙 (★최우선 적용):
  간편심사 Q3는 아래 KCD 코드 계열만 해당. 나머지는 모두 Q3 배정 절대 불가.
  허용: C00~C97·D00~D09(암) / I60~I62(뇌출혈) / I63~I64(뇌경색) / I20(협심증) / I21~I22(심근경색) / I05~I09·I34~I38(심장판막증) / K74(간경화)

  Q3에 절대 배정하면 안 되는 대표 질환:
  - 당뇨병 E10~E14 계열 → Q3 불가{q3_diabetes_note}
  - 고혈압 I10~I15 → Q3 불가
  - 무릎관절증 M17 / 척추협착 M48 → Q3 불가
  - 망막장애 H35 → Q3 불가
  - 위·대장 용종 K63.5 / K31 → Q3 불가
  - 메니에르 H81 / 위장출혈 K92 → Q3 불가
  - 발치 K08 / 피부질환 L98 → Q3 불가
  위 질환들이 Q3에 들어와 있으면 반드시 제거하고 올바른 질문으로 재배정하세요.

{step5_q4_exempt_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━
[6단계: weight(중요도) 배정]
━━━━━━━━━━━━━━━━━━━━━━━━━━
- critical: 암(C·D0계열)/뇌졸중(I60-64)/심근경색(I21-22)/협심증(I20)/간경화(K74)/심장판막(I05-09,I34-38)/에이즈(B20-24)/괴사성근막염
- high: 당뇨합병증/고혈압/신부전/간질환/정신질환/척추수술/관절치환
- mid: 용종절제/발치/단순 만성질환/30일이상 투약
- low: 단순 외래 통원/감기/염좌/치과 단순치료

반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON:
{{
  "flagged_items": [
    {{
      "date": "YYYY-MM-DD",
      "code": "정규화된 KCD코드 (예: E11.50)",
      "disease": "질병/수술명 (한글로 명확하게)",
      "hospital": "병원명",
      "duty_question": "{json_duty_q_values}",
      "reason": "고지 판단 사유 (구체적으로, 예: 대장내시경 용종절제술=수술 해당)",
      "is_inpatient": true또는false,
      "inpatient_days": 숫자또는0,
      "is_surgery": true또는false,
      "surgery_name": "수술명 또는 null",
      "med_days": 투약일수숫자또는0,
      "weight": "critical 또는 high 또는 mid 또는 low"
    }}
  ],
  "exempt_items": [],
  {json_hit_fields}
  "drug_change_hit": true또는false, "drug_change_reason": "변경된 약 정보 또는 없음",
  "total_flagged": 숫자,
  "health_verdict": "가능 또는 조건부 또는 불가",
  "health_reason": "판단 이유 한 줄",
  "recommend": "건강체 진행 가능 또는 인수 불가 가능성",
  "summary": "설계사를 위한 핵심 요약 2줄"
}}

절대 규칙: 응답은 반드시 {{ 로 시작하고 }} 로 끝나는 순수 JSON만 출력하세요.
설명, 주석, 마크다운 백틱, 전후 텍스트 일체 금지."""

    return system_prompt


def _build_medical_judgment_inputs(
    disease_stats: dict,
    _d3m_dt: datetime,
    _d1y_dt: datetime,
    today_str: str,
) -> tuple[list[dict], list[dict]]:
    """의학 판단(추가검사/치료종결) API 입력 2종을 구성."""
    # ── 의학 판단 입력 준비 ─────────────────────────────────────
    _mj_type1: list[dict] = []
    _mj_type2: list[dict] = []
    _seen_mj1: set[str] = set()
    _seen_mj2: set[str] = set()

    for _jck, _js in disease_stats.items():
        _jdc = (_js.get("diag_code") or _jck).strip()
        if not _jdc or _jdc in ("$", "해당없음"):
            continue
        _jname   = _js.get("name", "")
        _jlatest = _js.get("latest_date", "")

        _detail_test_events_1y = _recent_detail_test_events(_js, _d1y_dt)
        _detail_test_types_1y = _detail_test_type_count(_detail_test_events_1y)
        if (
            _detail_test_events_1y
            and (len(_detail_test_events_1y) >= 2 or _detail_test_types_1y >= 2)
            and _jdc not in _seen_mj1
        ):
            _seen_mj1.add(_jdc)
            _mj_type1.append({
                "disease_code":      _jdc,
                "disease_name":      _jname,
                "latest_date":       _jlatest,
                "reference_date":    today_str,
                "lookback":          "최근 1년",
                "candidate_rule":    "same disease code detail tests >=2 events or >=2 types",
                "test_event_count":  len(_detail_test_events_1y),
                "test_type_count":   _detail_test_types_1y,
                "detail_test_events": _detail_test_events_1y[:20],
            })

        _jdt = _parse_ymd(_jlatest)
        if _jdt and _jdt >= _d3m_dt and _jdc not in _seen_mj2:
            _seen_mj2.add(_jdc)
            _all_procs: set[str] = set()
            for _df_val in _js.get("_daily_facts", {}).values():
                _all_procs.update(_df_val.get("detail_proc_names", set()))
            _treatments = _sorted_strings(
                _all_procs | _js.get("tests_found", set()) | _js.get("surgeries", set())
            )[:15]
            _presc_list: list[dict] = []
            for _pd, _pdays in sorted(_js.get("med_dates_pharma", {}).items(), reverse=True)[:5]:
                _pdt2 = _parse_ymd(_pd)
                if _pdt2 and _pdt2 >= _d3m_dt and _pdays > 0:
                    _presc_list.append({"date": _pd, "days": _pdays})
            _recent_drugs = [d[:30] for d in _sorted_strings(_js.get("drug_names_in_90", set()))[:5]]
            _mj_type2.append({
                "disease_code":  _jdc,
                "disease_name":  _jname,
                "last_date":     _jlatest,
                "today":         today_str,
                "treatments":    [t[:40] for t in _treatments],
                "prescriptions": _presc_list,
                "recent_drugs":  _recent_drugs,
            })

    return _mj_type1, _mj_type2


def _apply_medical_judgment(
    disease_stats: dict,
    code_based_items: list[dict],
    _med_result: dict,
    _d1y_dt: datetime,
) -> None:
    """의학 판단 결과를 disease_stats·code_based_items에 반영(in-place)."""
    # ── 의학 판단 결과 → disease_stats 반영 ─────────────────────
    _at_results = _med_result.get("additional_tests", {})
    _to_results = _med_result.get("treatment_ongoing", {})
    for _jck, _js in disease_stats.items():
        _jdc = (_js.get("diag_code") or _jck).strip()
        if _jdc in _at_results:
            _js["_additional_test_result"] = _at_results[_jdc]
        if _jdc in _to_results:
            _js["_treatment_ongoing_result"] = _to_results[_jdc]

        _at = _js.get("_additional_test_result")
        if _at and bool(_at.get("is_additional_test")):
            _events_1y = _recent_detail_test_events(_js, _d1y_dt)
            if _events_1y:
                _event_dates = [e["date"] for e in _events_1y if e.get("date")]
                _test_names = _sorted_strings({e["name"] for e in _events_1y if e.get("name")})
                _med_dict = _js.get("med_dates_pharma_episode") or _js.get("med_dates_pharma", {})
                code_based_items.append({
                    "date": max(_event_dates) if _event_dates else _js.get("latest_date", ""),
                    "code": _jdc,
                    "disease": _js.get("name", "") or _jdc,
                    "hospital": " / ".join(_sorted_strings(_js.get("hospitals", set()))[:2]) or "정보 없음",
                    "duty_question": "Q2",
                    "reason": _at.get("reason") or (
                        f"1년 이내 세부진료 검사 {len(_events_1y)}회/"
                        f"{_detail_test_type_count(_events_1y)}종 - API 추가검사/재검사 판단"
                    ),
                    "is_inpatient": False,
                    "inpatient_days": 0,
                    "inpatient_count": 0,
                    "visit_count": _visit_count_in_range(_js, _d1y_dt),
                    "is_surgery": False,
                    "surgery_name": None,
                    "med_days": _max_presc(_med_dict, _d1y_dt),
                    "first_diagnosis_date": _js.get("first_date", ""),
                    "weight": "mid",
                    "_source": "medical_judgment",
                    "_rule_id": "R-H-Q2-TEST-API",
                    "_evidence": {
                        "api_reason": _at.get("reason", ""),
                        "test_type": _at.get("test_type", ""),
                        "test_event_count": len(_events_1y),
                        "test_type_count": _detail_test_type_count(_events_1y),
                        "test_names": _test_names[:10],
                        "test_dates": _event_dates,
                        "source": "detail+api",
                    },
                })



# ==========================================
# 분석 엔진
# ==========================================
async def run_analysis(active_files, product_type, reference_date, birthdate_pw, api_key) -> dict:
    """
    PDF 파일들을 분석하여 알릴의무 항목을 추출합니다.

    Returns dict with keys:
        ai_result, summary_reports, flagged_codes,
        prescription_end_details, drug_change_summary,
        analysis_today, parse_errors, retry_warnings, truncation_warning

    Raises:
        AnalysisError: 분석 실패 시
    """
    today = datetime(reference_date.year, reference_date.month, reference_date.day)
    _d3m_dt  = today - timedelta(days=90)
    _d1y_dt  = today - timedelta(days=365)
    _d5y_dt  = _subtract_years(today, 5)    # SURIT-004: 달력 기준 5년
    _d10y_dt = _subtract_years(today, 10)   # SURIT-004: 달력 기준 10년
    retry_warnings = []

    all_records, parse_errors = await _parse_all_pdfs(active_files, birthdate_pw)
    # ── disease_stats + raw_entries 빌드 ─────────────────────────
    disease_stats, cross_surgery_hints, date_warnings, raw_entries, lines_by_file = \
        build_disease_stats(all_records, today)
    del all_records
    gc.collect()

    parse_errors.extend(date_warnings)

    # ── 약 변경 감지 ──────────────────────────────────────────────
    drug_change_summary = detect_drug_changes(disease_stats, today)

    # ── 코드 기반 결정론적 알릴의무 ──────────────────────────────
    drug_change_groups = {
        dc["group"] for dc in drug_change_summary
        if dc.get("change_type") in ("약 종류 변경", "새 약 추가", "용량 증가")
    }
    code_based_items = _build_code_based_items(
        disease_stats=disease_stats,
        reference_date=today,
        product_type=product_type,
        drug_change_groups=drug_change_groups,
    )

    # ── 처방 종료일 계산 ─────────────────────────────────────────
    prescription_end_details, earliest_available_date = \
        compute_prescription_end_dates(disease_stats, today)

    # ── drug_change_text / presc_end_text 구성 ───────────────────
    today_str = today.strftime('%Y-%m-%d')
    d_3m  = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    d_1y  = (today - timedelta(days=365)).strftime('%Y-%m-%d')
    d_5y  = _subtract_years(today, 5).strftime('%Y-%m-%d')    # SURIT-004: 달력 기준 5년
    d_10y = _subtract_years(today, 10).strftime('%Y-%m-%d')   # SURIT-004: 달력 기준 10년

    drug_change_text = _build_drug_change_text(drug_change_summary)
    presc_end_text = _build_presc_end_text(prescription_end_details, earliest_available_date, today)
    lines_by_file_tagged = _build_tagged_entries(raw_entries, today, _d5y_dt, _d10y_dt)
    visit_count_lines = _build_visit_count_lines(disease_stats, _d10y_dt)
    first_diag_lines = _build_first_diag_lines(disease_stats)
    system_prompt = _build_system_prompt(product_type, today_str, d_3m, d_1y, d_5y, d_10y)
    _mj_type1, _mj_type2 = _build_medical_judgment_inputs(disease_stats, _d3m_dt, _d1y_dt, today_str)
    # ── Gemini API 호출 (PDF별 병렬 + 의학 판단 병렬) ────────────
    gemini_payloads = []
    truncated_files: list[str] = []
    for uf in active_files:
        fn = getattr(uf, "name", None) or getattr(uf, "filename", None) or "unknown.pdf"
        flines = lines_by_file_tagged.get(fn, [])
        rt_part = _finalize_raw_text_for_gemini(
            flines,
            visit_count_lines,
            cross_surgery_hints,
            first_diag_lines,
            drug_change_text,
            presc_end_text,
        )
        # SURIT-003: 초대용량 PDF로 AI 입력이 잘렸는지 감지 (잘림 로직은 불변)
        if _is_gemini_input_truncated(flines, rt_part):
            truncated_files.append(fn)
        gemini_payloads.append({
            "filename": fn,
            "raw_text": rt_part,
            "system_prompt": system_prompt,
            "today_str": today_str,
        })

    # SURIT-003: 잘림 발생 시 사용자 경고를 retry_warnings 채널로 노출
    truncation_warning = _build_truncation_warning(truncated_files)
    if truncation_warning:
        retry_warnings.append(truncation_warning)

    sem = asyncio.Semaphore(5)

    async def _guarded_gemini(pd: dict):
        async with sem:
            return await analyze_single_pdf(pd, product_type, reference_date, api_key)

    _all_api_results = await asyncio.gather(
        _call_medical_judgment(_mj_type1, _mj_type2, api_key),
        *[_guarded_gemini(pd) for pd in gemini_payloads],
        return_exceptions=True,
    )
    _med_result_raw = _all_api_results[0]
    gemini_out      = list(_all_api_results[1:])

    _med_result: dict = (
        _med_result_raw
        if isinstance(_med_result_raw, dict)
        else {"additional_tests": {}, "treatment_ongoing": {}}
    )
    if "_error" in _med_result:
        retry_warnings.append(
            "⚠️ 추가검사 여부·치료 종결 여부(알릴의무 Q2 등) 자동 판단을 완료하지 못했습니다. "
            "이 항목은 결과에서 누락됐을 수 있으니 진료 원자료로 직접 확인해 주세요."
        )

    ai_successes: list[dict] = []
    for i, go in enumerate(gemini_out):
        fn = gemini_payloads[i]["filename"]
        if isinstance(go, BaseException):
            retry_warnings.append(f"⚠️ {fn}: Gemini 병렬 태스크 예외 — {str(go)[:120]}")
            continue
        retry_warnings.extend(go.get("retry_warnings") or [])
        if go.get("error"):
            retry_warnings.append(f"⚠️ {fn}: {go['error']}")
        if go.get("ai_result"):
            ai_successes.append(go["ai_result"])

    if not ai_successes:
        raise AnalysisError("모든 PDF에 대한 AI 분석에 실패했습니다.")

    ai_result = _merge_ai_results(ai_successes)

    _apply_medical_judgment(disease_stats, code_based_items, _med_result, _d1y_dt)
    del system_prompt
    gc.collect()

    # ── summary_reports 빌드 ─────────────────────────────────────
    std_reports, easy_reports, flagged_codes, _ = build_summary_reports(
        disease_stats, code_based_items, ai_result, product_type, today,
    )
    summary_reports = std_reports  # 하위 호환

    # ── 전체 병력 요약 ─────────────────────────────────────────
    all_disease_summary = _build_all_disease_summary(disease_stats)

    # SURIT-BUG-008: 메리츠 간편보험 평가 제거. main.py 호환을 위해 빈 dict 반환.
    meritz_easy_result: dict = {}

    return {
        "ai_result":               ai_result,
        "summary_reports":         {k: list(v) for k, v in summary_reports.items()},
        "standard_reports":        {k: list(v) for k, v in std_reports.items()},
        "easy_reports":            {k: list(v) for k, v in easy_reports.items()},
        "all_disease_summary":     all_disease_summary,
        "flagged_codes":           flagged_codes,
        "prescription_end_details": prescription_end_details,
        "drug_change_summary":     drug_change_summary,
        "analysis_today":          today,
        "parse_errors":            parse_errors,
        "retry_warnings":          retry_warnings,
        "truncation_warning":      truncation_warning,
        "meritz_easy":             meritz_easy_result,
    }
