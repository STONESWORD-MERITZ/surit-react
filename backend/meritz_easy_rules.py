"""
메리츠화재 간편보험 예외질환 인수 룰 엔진

- 10년 이내 최대 5개 예외질환까지 인수 가능
- 각 질환별 경과기간/입원기준/수술기준 충족 시 예외 인정
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any

# ──────────────────────────────────────────────────────────────
# 룰 테이블
# 각 항목: (코드시작, 코드끝, 경과일수, 입원일수제한, 입원횟수제한, 수술기준)
#   입원일수/횟수 = -1 이면 제한없음
#   수술기준: 0=비수술, N=N회까지 허용, -1=제한없음
# ──────────────────────────────────────────────────────────────

_RULES_RAW: list[tuple[str, str, int, int, int, int]] = [
    # (start, end, elapsed_days, hosp_days_limit, hosp_count_limit, surgery_limit)
    ("A01", "A09", 7, 10, 2, 0),
    ("A15", "A18", 7, 10, 2, 0),
    ("A39", "A39", 7, 10, 2, 0),
    ("A40", "A40", 7, 10, 2, 0),
    ("A75", "A75", 7, 10, 2, 0),
    ("A80", "A80", 7, 10, 2, 0),
    ("A87", "A87", 7, 10, 2, 0),
    ("B00", "B00", 7, 10, 2, 0),
    ("B01", "B01", 7, 5, 2, 2),
    ("B02", "B02", 7, 10, 2, 0),
    ("B05", "B05", 7, 10, 2, 0),
    ("B08", "B082", 7, 5, 2, 2),
    ("B15", "B349", 7, 10, 2, 0),
    ("B351", "B351", 7, 5, 2, 2),
    ("B37", "B379", 7, 10, 2, 0),
    ("B95", "B99", 7, 10, 2, 0),
    ("D11", "D136", 7, 5, 2, 2),
    ("D14", "D140", 7, 10, 2, 0),
    ("D21", "D21", 7, 5, 2, 2),
    ("D22", "D24", 7, 5, 2, 1),
    ("D25", "D26", 7, 10, 2, 2),
    ("D27", "D30", 7, 10, 2, 2),
    ("E03", "E07", 7, 10, 2, 0),
    ("E890", "E890", 7, 10, 2, 0),
    ("G00", "G03", 7, 10, 2, 0),
    ("G44", "G44", 7, 10, 2, 0),
    ("G47", "G47", 7, 10, 2, 0),
    ("G51", "G519", 7, 10, 2, 2),
    ("G56", "G56", 7, 10, 2, 2),
    ("G57", "G57", 7, 10, 2, 2),
    ("G58", "G58", 7, 10, 2, 2),
    ("G60", "G60", 7, 10, 2, 2),
    ("G81", "G81", 7, 10, 2, 2),
    ("G82", "G82", 7, 10, 2, 2),
    ("H10", "H10", 7, 10, 2, 0),
    ("H11", "H119", 7, 10, 2, 2),
    ("H15", "H18", 7, 10, 2, 0),
    ("H20", "H21", 7, 10, 2, 0),
    ("H25", "H28", 7, 10, 2, 2),
    ("H33", "H36", 7, 10, 2, 2),
    ("H40", "H40", 7, 10, 2, 2),
    ("H43", "H43", 7, 10, 2, 2),
    ("H50", "H50", 7, 10, 2, 2),
    ("H52", "H54", 7, 10, 2, 2),
    ("H60", "H75", 7, 10, 2, 2),
    ("H80", "H80", 7, 10, 2, 0),
    ("H81", "H819", 7, 10, 2, 0),
    ("H83", "H832", 7, 10, 2, 0),
    ("I80", "I80", 7, 10, 2, 2),
    ("I83", "I83", 7, 10, 2, 2),
    ("I861", "I861", 7, 10, 2, 2),
    ("I87", "I87", 7, 10, 2, 2),
    ("J00", "J06", 7, 10, 2, 0),
    ("J10", "J18", 7, 10, 2, 0),
    ("J20", "J21", 7, 10, 2, 0),
    ("J30", "J34", 7, 10, 2, 2),
    ("J35", "J351", 7, 10, 2, 1),
    ("J36", "J39", 7, 10, 2, 1),
    ("J40", "J40", 7, 10, 2, 0),
    ("J93", "J93", 7, 10, 2, 0),
    ("K00", "K14", 7, -1, -1, -1),
    ("K20", "K21", 7, 10, 2, 0),
    ("K25", "K31", 7, 10, 2, 0),
    ("K35", "K38", 7, 10, 1, 1),
    ("K40", "K46", 7, 10, 2, 2),
    ("K50", "K529", 7, 10, 2, 0),
    ("K55", "K599", 7, 10, 2, 0),
    ("K61", "K63", 7, 10, 2, 2),
    ("K65", "K67", 7, 10, 2, 0),
    ("L01", "L08", 7, 10, 2, 0),
    ("L10", "L43", 7, 10, 2, 0),
    ("L50", "L60", 7, 15, -1, 0),
    ("L72", "L75", 7, 5, 2, 2),
    ("L80", "L98", 7, 10, 2, 0),
    ("M00", "M00", 7, 10, 2, 2),
    ("M10", "M10", 7, 10, 2, 2),
    ("M23", "M23", 7, 10, 2, 2),
    ("M47", "M54", 7, 10, 2, 2),
    ("M62", "M79", 7, 10, 1, 1),
    ("N81", "N98", 7, 10, 2, 1),
    ("O00", "O08", 7, -1, -1, -1),
    ("O10", "O29", 7, -1, -1, -1),
    ("O30", "O48", 7, -1, -1, -1),
    ("O60", "O92", 7, -1, -1, -1),
    ("O95", "O99", 7, -1, -1, -1),
    ("S00", "S09", 7, 15, -1, 0),
    ("S11", "S91", 7, 15, -1, 0),
    ("S12", "S92", 7, 15, -1, 1),
    ("S13", "S93", 7, 15, -1, 0),
    ("S41", "S99", 7, 15, -1, 0),
    ("T15", "T19", 7, 15, -1, 2),
    ("T20", "T32", 7, 15, -1, 0),
    ("V01", "V99", 7, 15, -1, 1),
    ("W00", "W99", 7, 15, -1, 1),
    ("X20", "X59", 7, 15, -1, 1),
    ("U071", "U072", 7, 15, 2, 0),
    ("U08", "U09", 7, 15, 2, 0),
    ("U10", "U12", 7, 15, 2, 0),
    ("Z31", "Z31", 7, 10, 2, 1),
    ("Z32", "Z32", 7, 10, 2, 1),
    ("Z511", "Z511", 7, 10, 2, 2),
    ("Z521", "Z529", 7, 10, 2, 1),
    ("Z53", "Z53", 7, 10, 2, 0),
    ("Z761", "Z761", 7, 10, 2, 0),
]


def _strip_code(c: str) -> str:
    """코드에서 점/하이픈 제거 후 대문자 변환 (normalize_code와 동일 정규화)"""
    # OCR 노이즈(쉼표, 중점, 특수문자 등)를 제거해 코드 비교를 안정화
    return re.sub(r"[^A-Z0-9]", "", str(c).upper())


def _code_sort_key(code: str) -> tuple[str, int]:
    """코드를 (알파벳, 숫자) 튜플로 변환하여 범위 비교 가능하게 함"""
    code = _strip_code(code)
    if not code:
        return ("", 0)
    alpha = "".join(ch for ch in code if ch.isalpha())
    digits = "".join(ch for ch in code if ch.isdigit())
    return (alpha, int(digits) if digits else 0)


def _code_in_range(code: str, start: str, end: str) -> bool:
    """normalized code가 [start, end] 범위 안에 있는지 확인"""
    c = _code_sort_key(code)
    s = _code_sort_key(start)
    e = _code_sort_key(end)
    if not c[0]:
        return False
    # 알파벳 부분이 범위에 포함되어야 함
    if c[0] < s[0] or c[0] > e[0]:
        return False
    if c[0] == s[0] == e[0]:
        return s[1] <= c[1] <= e[1]
    if c[0] == s[0]:
        return c[1] >= s[1]
    if c[0] == e[0]:
        return c[1] <= e[1]
    return True


def find_rule(code: str) -> tuple | None:
    """코드에 매칭되는 룰을 찾음. 없으면 None."""
    code = _strip_code(code)
    if not code:
        return None
    for start, end, elapsed, hosp_days, hosp_count, surg_limit in _RULES_RAW:
        if _code_in_range(code, start, end):
            return (start, end, elapsed, hosp_days, hosp_count, surg_limit)
    return None


# ──────────────────────────────────────────────────────────────
# 판정 로직
# ──────────────────────────────────────────────────────────────

def _parse_dt(d: str) -> datetime | None:
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def evaluate_disease(
    code: str,
    disease_stat: dict[str, Any],
    reference_date: datetime,
) -> dict[str, Any] | None:
    """
    단일 질환코드에 대해 메리츠 간편 예외질환 인수 가능 여부를 판정.

    Returns:
        None: 해당 코드에 매칭 룰 없음
        dict: {
            "code": str,
            "rule_range": str,
            "eligible": bool,
            "reason": str,
            "elapsed_ok": bool,
            "hosp_ok": bool,
            "surgery_ok": bool,
            "total_hosp_days": int,
            "total_hosp_count": int,
            "total_surgery_count": int,
        }
    """
    rule = find_rule(code)
    if rule is None:
        return None

    start, end, elapsed_days, hosp_days_limit, hosp_count_limit, surg_limit = rule
    rule_range = f"{start}~{end}" if start != end else start

    ten_years_ago = reference_date - timedelta(days=3650)

    # --- 1) 경과기간 체크 ---
    # 치료종결일(latest_date) + 경과기간 이후여야 인수 가능
    latest = disease_stat.get("latest_date", "2000-01-01")
    latest_dt = _parse_dt(latest)
    elapsed_ok = True
    if latest_dt:
        available_date = latest_dt + timedelta(days=elapsed_days)
        if available_date > reference_date:
            elapsed_ok = False

    # --- 2) 입원기준 체크 (10년 이내) ---
    hosp_ok = True
    total_hosp_days = 0
    total_hosp_count = 0

    inpatient_dates = disease_stat.get("inpatient_dates", set())
    # 10년 이내 입원 날짜 필터
    dates_in_10y = []
    for d in inpatient_dates:
        dt = _parse_dt(d)
        if dt and dt >= ten_years_ago:
            dates_in_10y.append(d)

    total_hosp_count = len(dates_in_10y)
    # 입원일수: _inpatient_days_map에서 날짜별 내원일수 합산
    inp_days_map = disease_stat.get("_inpatient_days_map", {})
    total_hosp_days = sum(inp_days_map.get(d, 1) for d in dates_in_10y) if dates_in_10y else 0

    if hosp_days_limit != -1 and total_hosp_days > hosp_days_limit:
        hosp_ok = False
    if hosp_count_limit != -1 and total_hosp_count > hosp_count_limit:
        hosp_ok = False

    # --- 3) 수술기준 체크 (10년 이내) ---
    surgery_ok = True
    surgery_dates = disease_stat.get("surgery_dates", set())
    surgery_dates_in_10y = []
    for d in surgery_dates:
        dt = _parse_dt(d)
        if dt and dt >= ten_years_ago:
            surgery_dates_in_10y.append(d)
    total_surgery_count = len(surgery_dates_in_10y)

    if surg_limit == 0:
        # 비수술: 수술 있으면 미인수
        if total_surgery_count > 0:
            surgery_ok = False
    elif surg_limit == -1:
        # 제한없음
        pass
    else:
        # N회까지 허용
        if total_surgery_count > surg_limit:
            surgery_ok = False

    eligible = elapsed_ok and hosp_ok and surgery_ok

    # 사유 구성
    reasons = []
    if not elapsed_ok:
        reasons.append(f"경과기간 미충족(치료종결일 {latest} + {elapsed_days}일 미경과)")
    if not hosp_ok:
        parts = []
        if hosp_days_limit != -1 and total_hosp_days > hosp_days_limit:
            parts.append(f"입원일수 {total_hosp_days}일>{hosp_days_limit}일")
        if hosp_count_limit != -1 and total_hosp_count > hosp_count_limit:
            parts.append(f"입원횟수 {total_hosp_count}회>{hosp_count_limit}회")
        reasons.append("입원기준 초과(" + ", ".join(parts) + ")")
    if not surgery_ok:
        if surg_limit == 0:
            reasons.append(f"비수술 기준 위반(수술 {total_surgery_count}건)")
        else:
            reasons.append(f"수술횟수 초과({total_surgery_count}회>{surg_limit}회)")

    reason = "; ".join(reasons) if reasons else "모든 조건 충족"

    return {
        "code": code,
        "name": disease_stat.get("name", ""),
        "rule_range": rule_range,
        "eligible": eligible,
        "reason": reason,
        "elapsed_ok": elapsed_ok,
        "hosp_ok": hosp_ok,
        "surgery_ok": surgery_ok,
        "total_hosp_days": total_hosp_days,
        "total_hosp_count": total_hosp_count,
        "total_surgery_count": total_surgery_count,
    }


# ──────────────────────────────────────────────────────────────
# 추천 고지 시나리오 계산
# ──────────────────────────────────────────────────────────────

def _compute_recommended_disclosure(
    code: str,
    disease_stat: dict[str, Any],
    reference_date: datetime,
) -> int | None:
    """
    인수거절 케이스에 대해 가장 오래된 건부터 제외하면서
    몇 년부터 고지하면 통과하는지 계산.

    Returns: 통과 가능한 가장 이른 연도 (int) 또는 None (불가능)
    """
    rule = find_rule(code)
    if rule is None:
        return None

    _, _, elapsed_days, hosp_days_limit, hosp_count_limit, surg_limit = rule
    ten_years_ago = reference_date - timedelta(days=3650)

    # 입원 기록 수집 (날짜, 실제 입원일수)
    inpatient_dates = disease_stat.get("inpatient_dates", set())
    inp_days_map = disease_stat.get("_inpatient_days_map", {})
    inp_records: list[tuple[str, int]] = []
    for d in sorted(inpatient_dates):
        dt = _parse_dt(d)
        if dt and dt >= ten_years_ago:
            inp_records.append((d, inp_days_map.get(d, 1)))

    # 수술 기록
    surgery_dates = disease_stat.get("surgery_dates", set())
    surg_records: list[str] = sorted(
        d for d in surgery_dates
        if _parse_dt(d) and _parse_dt(d) >= ten_years_ago
    )

    # 가장 오래된 건부터 하나씩 제외하며 시뮬레이션
    for exclude_count in range(len(inp_records) + len(surg_records) + 1):
        # 입원 기록에서 오래된 것부터 제외
        remaining_inp = inp_records[exclude_count:]
        remaining_surg = surg_records[exclude_count:]

        # 입원 체크 — h_days 는 실제 입원일수 합, h_count 는 입원 건수
        h_ok = True
        h_days = sum(days for _, days in remaining_inp)
        h_count = len(remaining_inp)
        if hosp_days_limit != -1 and h_days > hosp_days_limit:
            h_ok = False
        if hosp_count_limit != -1 and h_count > hosp_count_limit:
            h_ok = False

        # 수술 체크
        s_ok = True
        s_count = len(remaining_surg)
        if surg_limit == 0 and s_count > 0:
            s_ok = False
        elif surg_limit > 0 and s_count > surg_limit:
            s_ok = False

        if h_ok and s_ok:
            if exclude_count == 0:
                return None  # 이미 통과
            # 제외 기준 시점 = 제외된 마지막 건의 다음 해
            all_dates = sorted(
                [r[0] for r in inp_records[:exclude_count]] +
                surg_records[:exclude_count]
            )
            if all_dates:
                cutoff = all_dates[-1]
                cutoff_dt = _parse_dt(cutoff)
                if cutoff_dt:
                    # 이 날짜 이후부터 고지하면 통과
                    return cutoff_dt.year + 1
            return None

    return None


# ──────────────────────────────────────────────────────────────
# 메인 평가 함수 (analyzer.py에서 호출)
# ──────────────────────────────────────────────────────────────

def evaluate_meritz_easy(
    disease_stats: dict[str, dict[str, Any]],
    reference_date: datetime,
) -> dict[str, Any]:
    """
    전체 disease_stats를 대상으로 메리츠 간편 예외질환 인수 여부를 판정.

    Returns: {
        "meritz_easy_eligible": bool,
        "exception_diseases_count": int,
        "exception_diseases": list[dict],
        "rejected_diseases": list[dict],
        "recommended_disclosure_year": int | None,
        "detail_message": str,
    }
    """
    exception_results: list[dict] = []
    rejected_results: list[dict] = []

    ten_years_ago = reference_date - timedelta(days=3650)

    for group_key, stat in disease_stats.items():
        code = stat.get("diag_code", "") or group_key

        # 간편 2번은 입원/수술만 해당 — 10년 이내 입원·수술 기록이 없으면 스킵
        inp_in_10y = [
            d for d in stat.get("inpatient_dates", set())
            if _parse_dt(d) and _parse_dt(d) >= ten_years_ago
        ]
        surg_in_10y = [
            d for d in stat.get("surgery_dates", set())
            if _parse_dt(d) and _parse_dt(d) >= ten_years_ago
        ]
        if not inp_in_10y and not surg_in_10y:
            continue  # 외래 전용 — 간편 2번 대상 아님

        result = evaluate_disease(code, stat, reference_date)
        if result is None:
            continue  # 룰에 해당하지 않는 코드

        if result["eligible"]:
            exception_results.append(result)
        else:
            # 추천 고지연도 계산
            rec_year = _compute_recommended_disclosure(code, stat, reference_date)
            result["recommended_year"] = rec_year
            rejected_results.append(result)

    # 5개 제한 체크
    total_exception = len(exception_results)
    within_limit = total_exception <= 5

    # 전체 인수 가능 여부: 거절 건이 없고, 예외질환 5개 이하
    eligible = len(rejected_results) == 0 and within_limit

    # 추천 고지연도: 거절 건 중 가장 늦은 연도
    rec_years = [r["recommended_year"] for r in rejected_results if r.get("recommended_year")]
    recommended_year = max(rec_years) if rec_years else None

    # 상세 메시지 구성
    lines = []
    if exception_results:
        lines.append(f"[메리츠 간편 예외질환] 인수가능 {len(exception_results)}건")
        for r in exception_results:
            lines.append(f"  ✓ {r['code']}({r['name']}) — {r['rule_range']} 범위, {r['reason']}")
    if rejected_results:
        lines.append(f"[메리츠 간편 예외질환] 미인수 {len(rejected_results)}건")
        for r in rejected_results:
            rec_str = f", 추천고지: {r['recommended_year']}년~" if r.get("recommended_year") else ""
            lines.append(f"  ✗ {r['code']}({r['name']}) — {r['reason']}{rec_str}")
    if not within_limit:
        lines.append(f"  ※ 예외질환 {total_exception}개 — 5개 초과로 인수 거절 가능성")
    if recommended_year:
        lines.append(f"  → 추천: {recommended_year}년부터 고지 시 통과 가능")

    return {
        "meritz_easy_eligible": eligible,
        "exception_diseases_count": total_exception,
        "exception_diseases": exception_results,
        "rejected_diseases": rejected_results,
        "recommended_disclosure_year": recommended_year,
        "detail_message": "\n".join(lines),
    }
