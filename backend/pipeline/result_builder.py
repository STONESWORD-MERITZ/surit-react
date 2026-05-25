"""summary_reports 빌드 — analyzer.py 에서 이동."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from .helpers import (
    _dts_in_range,
    _inpatient_end_dates_in_range,
    _inpatient_periods_in_range,
    _max_presc,
    _parse_ymd,
    _sorted_strings,
    _subtract_years,
    _visit_count_in_range,
    format_kcd_code,
    is_simple_q3_allowed,
    normalize_code,
)

# 비-질병 항목 차단용 (merge 단계 이중 안전망)
_KCD_MERGE_RE = re.compile(r"^[A-Z]\d{2,4}[A-Z0-9]?$")
_NON_DISEASE_NAME_PATTERNS_MERGE = (
    "진찰료", "재진", "초진",
    "조제료", "약국관리료", "약제비",
    "응급및회송료", "외래환자의약품관리료",
    "주사료", "주사기료",
    "검사료", "방사선료", "마취료", "이학요법료",
    "처치및수술", "처치 및수술", "처치및 수 술",
    "재료대", "행위료", "기본진료료", "방문당",
)


def _make_merged_item(item: dict, q: str, code_override: str = "") -> dict:
    return {
        "dates":          [item.get("date", "")],
        "code":           code_override or item.get("code", "-"),
        "name":           item.get("disease", ""),
        "duty_question":  q,
        "reason":         item.get("reason", ""),
        "is_inpatient":   item.get("is_inpatient", False),
        "inpatient_days": item.get("inpatient_days", 0),
        "inpatient_count": item.get("inpatient_count", 0),
        "visit_count":    item.get("visit_count", 0),
        "first_diagnosis_date": item.get("first_diagnosis_date", ""),
        "is_surgery":     item.get("is_surgery", False),
        "surgery_name":   item.get("surgery_name"),
        "surgery_dates":  [item.get("date", "")] if item.get("is_surgery") else [],
        "med_days":       item.get("med_days", 0),
        "weight":         item.get("weight", "mid"),
        "hospitals":      [item.get("hospital", "")],
    }


def _merge_item_into(m: dict, item: dict) -> None:
    if item.get("date"):
        m["dates"].append(item.get("date", ""))
    if item.get("reason") and item["reason"] not in m.get("reason", ""):
        m["reason"] = (m.get("reason", "") + " / " + item["reason"]).strip(" /")
    if item.get("is_surgery"):
        m["is_surgery"] = True
        if item.get("date"):
            m["surgery_dates"].append(item.get("date", ""))
        if item.get("surgery_name"):
            m["surgery_name"] = item.get("surgery_name")
    m["inpatient_days"] = max(m["inpatient_days"], item.get("inpatient_days", 0))
    m["inpatient_count"] = max(m["inpatient_count"], item.get("inpatient_count", 0))
    m["visit_count"] = max(m["visit_count"], item.get("visit_count", 0))
    if item.get("first_diagnosis_date") and item["first_diagnosis_date"] < m.get("first_diagnosis_date", "2099-12-31"):
        m["first_diagnosis_date"] = item["first_diagnosis_date"]
    m["med_days"] = max(m["med_days"], item.get("med_days", 0))
    weight_order = {"critical": 4, "high": 3, "mid": 2, "low": 1}
    if weight_order.get(item.get("weight", "low"), 0) > weight_order.get(m["weight"], 0):
        m["weight"] = item.get("weight", "mid")
    if item.get("hospital") and item["hospital"] not in m["hospitals"]:
        m["hospitals"].append(item["hospital"])


def _merged_item_sort_key(entry) -> tuple:
    (code, q), item = entry
    dates = _sorted_strings(item.get("dates", []))
    return (q, code, dates[0] if dates else "", item.get("name", ""))


def _build_reports_for_product(merged_items, disease_stats, product_type, d3m, d1y, d10y, d5y):
    """merged_items + disease_stats → (summary_reports, flagged_codes)."""
    is_easy = product_type == "간편심사 (유병자 3-5-5 기준)"

    if is_easy:
        _q_since = {"Q1": d3m, "Q2": d10y, "Q3": d5y}
        q_labels = {
            "Q1": "[간편1번질문] 3개월 이내 진단·약 변경",
            "Q2": "[간편2번질문] 10년 이내 입원/수술",
            "Q3": "[간편3번질문] 5년 이내 중대질병",
        }
    else:
        _q_since = {"Q1": d3m, "Q2": d1y, "Q3": d10y, "Q4": d5y}
        q_labels = {
            "Q1": "[1번질문] 3개월 이내 진단·입원·수술·투약",
            "Q2": "[2번질문] 1년 이내 추가검사(재검사)",
            "Q3": "[참고] 최근 10년 입원·수술·7회이상통원·30일이상투약 (청약서 3번 문항은 5년 기준 — 별도 대조 필요)",
            "Q4": "[4번질문] 5년 이내 중대질병",
        }

    summary_reports = defaultdict(list)
    flagged_codes   = set()
    seen_pairs      = set()

    for merge_key, m in sorted(merged_items.items(), key=_merged_item_sort_key):
        code_key = m["code"]
        q_orig   = m["duty_question"]

        if is_easy:
            if q_orig == "Q2":
                continue
            elif q_orig == "Q3":
                _ds_chk = disease_stats.get(code_key)
                has_inp  = bool(_ds_chk and _dts_in_range(_ds_chk.get("inpatient_dates", set()), d10y))
                has_surg = m.get("is_surgery", False) or bool(
                    _ds_chk and _dts_in_range(_ds_chk.get("surgery_dates", set()), d10y))
                if not (has_inp or has_surg):
                    continue
                q = "Q2"
            elif q_orig == "Q4":
                if not is_simple_q3_allowed(code_key):
                    continue
                q = "Q3"
            else:
                q = q_orig
        else:
            q = q_orig

        if q not in q_labels:
            continue

        pair = (code_key, q)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        q_title  = q_labels[q]
        since_dt = _q_since.get(q, d10y)
        _ds      = disease_stats.get(code_key)

        if _ds:
            _inpatient_end_dates = _inpatient_end_dates_in_range(_ds, since_dt)
            _all_dates   = (
                _ds.get("visit_dates", set())
                | _ds.get("inpatient_dates", set())
                | _inpatient_end_dates
                | _ds.get("surgery_dates", set())
            )
            _in_range    = _dts_in_range(_all_dates, since_dt)
            first_date   = _in_range[0]  if _in_range else ""
            latest_date  = _in_range[-1] if _in_range else ""
            _fd = _ds.get("first_date", "2099-12-31")
            first_diagnosis_date = _fd if _fd and _fd != "2099-12-31" else first_date

            _ds_inp_dates      = _dts_in_range(_ds.get("inpatient_dates", set()), since_dt)
            _ds_inp_periods    = _inpatient_periods_in_range(_ds, since_dt)
            _ds_inp_map        = _ds.get("_inpatient_days_map", {})
            ds_inpatient_days  = sum(_ds_inp_map.get(d, 1) for d in _ds_inp_dates) if _ds_inp_dates else 0
            ds_inpatient_count = len(_ds_inp_dates)
            ds_visit_count     = _visit_count_in_range(_ds, since_dt)
            ds_med_days        = _max_presc(_ds.get("med_dates_pharma", {}), since_dt)
        else:
            dates_sorted       = sorted([d for d in m["dates"] if d])
            first_date         = dates_sorted[0]  if dates_sorted else ""
            latest_date        = dates_sorted[-1] if dates_sorted else ""
            first_diagnosis_date = first_date
            ds_inpatient_days  = m["inpatient_days"]
            ds_inpatient_count = m.get("inpatient_count", 0)
            ds_visit_count     = m.get("visit_count", 0)
            ds_med_days        = m["med_days"]
            _ds_inp_dates      = []
            _ds_inp_periods    = []

        _chojin          = _ds["chojin_count"]  if _ds else 0
        _jaejin          = _ds["jaejin_count"]  if _ds else 0
        _procedures      = _sorted_strings(_ds.get("procedures", set()) or []) if _ds else []
        _proc_dates      = sorted(_ds.get("procedure_dates", set()) or []) if _ds else []
        _surg_susp       = _sorted_strings(_ds.get("surgery_suspected_names", set()) or []) if _ds else []
        _surg_susp_dates = sorted(_ds.get("surgery_suspected_dates", set()) or []) if _ds else []

        _at_res = _ds.get("_additional_test_result") if _ds else None
        _to_res = _ds.get("_treatment_ongoing_result") if _ds else None

        if _at_res is not None:
            _add_test_hit    = bool(_at_res.get("is_additional_test"))
            _add_test_reason = _at_res.get("reason", "")
            _additional_tests = [_at_res.get("test_type", "재검사")] if _add_test_hit else []
        else:
            _add_test_hit    = False
            _add_test_reason = ""
            _additional_tests = [t[:50] for t in _sorted_strings(_ds.get("tests_found", set()) or [])[:8]] if _ds else []

        if _to_res is not None:
            _tx_ongoing        = bool(_to_res.get("is_ongoing"))
            _tx_ongoing_reason = _to_res.get("reason", "")
        else:
            _tx_ongoing        = None
            _tx_ongoing_reason = ""

        flagged_codes.add(code_key)
        summary_reports[q_title].append({
            "first_date":              first_date,
            "latest_date":             latest_date,
            "first_diagnosis_date":    first_diagnosis_date,
            "code":                    m["code"],
            "display_code":            format_kcd_code(m["code"]),
            "name":                    m["name"] or (_ds.get("name", "") if _ds else ""),
            "visit":                   ds_visit_count,
            "chojin_count":            _chojin,
            "jaejin_count":            _jaejin,
            "total_clinic_visit":      _chojin + _jaejin if (_chojin + _jaejin) > 0 else ds_visit_count,
            "med_days":                ds_med_days,
            "med_days_30plus":         ds_med_days >= 30,
            "inpatient":               ds_inpatient_days,
            "inpatient_count":         ds_inpatient_count,
            "inpatient_dates":         _ds_inp_dates if _ds and _ds_inp_dates else [],
            "inpatient_periods":       _ds_inp_periods if _ds and _ds_inp_periods else [],
            "surgeries":               {m["surgery_name"]} if m["is_surgery"] and m["surgery_name"] else ({"수술"} if m["is_surgery"] else set()),
            "surgery_dates":           sorted(set(m["surgery_dates"])),
            "surgery_count":           len(set(m["surgery_dates"])) if m["is_surgery"] else 0,
            "procedures":              _procedures,
            "procedure_dates":         _proc_dates,
            "surgery_suspected":       _surg_susp,
            "surgery_suspected_dates": _surg_susp_dates,
            "additional_tests":        _additional_tests,
            "additional_test_hit":     _add_test_hit,
            "additional_test_reason":  _add_test_reason,
            "treatment_ongoing":       _tx_ongoing,
            "treatment_ongoing_reason": _tx_ongoing_reason,
            "drug_change_in_3m":       _ds.get("drug_change_in_3m", False) if _ds else False,
            "hospitals":               m["hospitals"],
            "first_hospital":          (_ds.get("hospital_dates", {}).get(first_diagnosis_date, "")
                                        or _ds.get("hospital_dates", {}).get(first_date, "")) if _ds else "",
            "last_hospital":           _ds.get("hospital_dates", {}).get(latest_date, "") if _ds else "",
            "detail":                  m["reason"],
        })

    return summary_reports, flagged_codes


def _build_all_disease_summary(disease_stats):
    """disease_stats 전체를 날짜순으로 정리한 리스트 반환."""
    result = []
    for code_key, s in sorted(disease_stats.items(), key=lambda kv: (kv[1].get("first_date", ""), kv[0])):
        if code_key.startswith("PHARMA|"):
            continue
        all_dates = sorted(
            s.get("visit_dates", set())
            | s.get("inpatient_dates", set())
            | _inpatient_end_dates_in_range(s, datetime.min)
            | s.get("surgery_dates", set())
        )
        first_date  = all_dates[0]  if all_dates else (s.get("first_date", "") or "")
        latest_date = all_dates[-1] if all_dates else (s.get("latest_date", "") or "")
        if first_date and first_date == "2099-12-31":
            first_date = ""

        inp_map   = s.get("_inpatient_days_map", {})
        inp_dates = sorted(s.get("inpatient_dates", set()))
        inpatient_days = sum(inp_map.get(d, 1) for d in inp_dates) if inp_dates else 0

        result.append({
            "code":            s.get("diag_code") or code_key.split("|")[0],
            "display_code":    format_kcd_code(s.get("diag_code") or code_key.split("|")[0]),
            "name":            s.get("name", ""),
            "first_date":      first_date,
            "latest_date":     latest_date,
            "visit_count":     len(s.get("visit_events") or s.get("visit_dates", set())),
            "inpatient_count": len(inp_dates),
            "inpatient_days":  inpatient_days,
            "inpatient_periods": _inpatient_periods_in_range(s, datetime.min),
            "surgery_count":   len(s.get("surgery_dates", set())),
            "med_days":        _max_presc(s.get("med_dates_pharma", {}), datetime.min),
            "hospitals":       sorted(s.get("hospitals", set())),
        })

    result.sort(key=lambda x: x.get("latest_date") or "0000", reverse=True)
    return result


def build_summary_reports(
    disease_stats: dict,
    code_based_items: list[dict],
    ai_result: dict,
    product_type: str,
    today: datetime,
) -> tuple[dict, set, dict]:
    """
    merged_items 빌드 + (표준/간편) summary_reports 생성.

    Returns:
        std_reports    : dict[str, list]
        easy_reports   : dict[str, list]
        flagged_codes  : set[str]
        merged_items   : dict[(code, q), item]
    """
    from datetime import timedelta

    _d3m_dt  = today - timedelta(days=90)
    _d1y_dt  = today - timedelta(days=365)
    _d5y_dt  = _subtract_years(today, 5)    # SURIT-004: 달력 기준 5년
    _d10y_dt = _subtract_years(today, 10)   # SURIT-004: 달력 기준 10년

    merged_items: dict = {}
    code_claimed: set  = set()

    for item in (code_based_items + ai_result.get("flagged_items", [])):
        _it_code = (item.get("code") or "").strip().upper()
        _it_name = (item.get("disease") or "").strip()
        if not _KCD_MERGE_RE.match(_it_code):
            continue
        if _it_name and any(pat in _it_name for pat in _NON_DISEASE_NAME_PATTERNS_MERGE):
            continue
        q_raw    = item.get("duty_question", "Q1")
        raw_code_key = item.get("code", item.get("disease", "unknown"))
        code_key = normalize_code(raw_code_key) or raw_code_key
        q_list   = [q.strip() for q in re.split(r"[,/\s]+", q_raw) if re.match(r"Q\d+", q.strip())]
        if not q_list:
            q_list = [q_raw.strip()]
        source = item.get("_source", "ai")

        for q in q_list:
            if q not in ("Q1", "Q2", "Q3", "Q4"):
                continue

            item_dt = _parse_ymd(item.get("date", ""))
            q_since_map = {"Q1": _d3m_dt, "Q2": _d1y_dt, "Q3": _d10y_dt, "Q4": _d5y_dt}
            since_dt = q_since_map.get(q)
            if since_dt and (not item_dt or item_dt < since_dt):
                continue

            merge_key = (code_key, q)

            if source == "code":
                code_claimed.add(merge_key)
                if merge_key not in merged_items:
                    merged_items[merge_key] = _make_merged_item(item, q, code_key)
                else:
                    _merge_item_into(merged_items[merge_key], item)
                continue

            if merge_key in code_claimed:
                continue

            if merge_key not in merged_items:
                merged_items[merge_key] = _make_merged_item(item, q, code_key)
            else:
                _merge_item_into(merged_items[merge_key], item)

    std_reports, std_flagged = _build_reports_for_product(
        merged_items, disease_stats,
        "건강체/표준체 (일반심사)",
        _d3m_dt, _d1y_dt, _d10y_dt, _d5y_dt,
    )
    easy_reports, easy_flagged = _build_reports_for_product(
        merged_items, disease_stats,
        "간편심사 (유병자 3-5-5 기준)",
        _d3m_dt, _d1y_dt, _d10y_dt, _d5y_dt,
    )

    flagged_codes = std_flagged | easy_flagged
    return std_reports, easy_reports, flagged_codes, merged_items
