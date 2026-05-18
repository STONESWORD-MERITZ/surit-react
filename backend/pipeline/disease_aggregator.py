"""disease_stats 빌드 + 약 변경 감지 + 처방 종료일 계산 — analyzer.py 에서 이동."""
from __future__ import annotations

import gc
import re
from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd

from .helpers import (
    PROCEDURE_COST_THRESHOLD,
    SURGERY_COST_THRESHOLD,
    _add_days,
    _clean_disease_name,
    _cross_key,
    _is_confirmed_surgery_cost_kw,
    _is_procedure_kw,
    _is_surgery_match,
    _keep_basic_general_row,
    _sorted_strings,
    _to_int_cost,
    disclosure_group_code,
    disclosure_group_name,
    extract_drug_info,
    get_diagnosis_code,
    get_diagnosis_name,
    get_val,
    nhis_surg_keywords,
    normalize_code,
    parse_date,
    row_is_junk,
    test_keywords,
)


def new_disease():
    return {
        "visit_dates": set(), "visit_events": [], "med_dates_basic": {}, "med_dates_pharma": {},
        "med_dates_pharma_episode": {},
        "drug_names_in_90": set(), "drug_names_before_90": set(),
        "tests_found": set(), "test_events": [], "inpatient_dates": set(), "inpatient_periods": [],
        "surgeries": set(), "surgery_dates": set(), "hospitals": set(),
        "procedures": set(),
        "procedure_dates": set(),
        "surgery_suspected_names": set(),
        "surgery_suspected_dates": set(),
        "_daily_facts": {},
        "_inpatient_days_map": {},
        "chojin_count": 0,
        "jaejin_count": 0,
        "drug_change_in_3m": False,
        "hospital_dates": {},
        "first_date": "2099-12-31", "latest_date": "2000-01-01",
        "diag_code": "", "name": "", "has_pharma": False,
    }


def build_disease_stats(
    records: list[dict],
    today: datetime,
) -> tuple[dict, list[str], list[str], list[tuple[str, str]], dict[str, list[str]]]:
    """
    파싱된 records 로부터 disease_stats + AI 전달용 raw_entries 빌드.

    Returns:
        disease_stats        : dict[group_key, disease_record]
        cross_surgery_hints  : list[str]
        date_warnings        : list[str]  — 날짜 파싱 실패/미래 날짜 경고
        raw_entries          : list[(fname, line)]  — AI raw_text 생성용
        lines_by_file        : dict[fname, list[str]]
    """
    df = pd.DataFrame(records)
    if "_ftype" in df.columns:
        ftype_order = {"basic": 0, "nhis": 0, "unknown": 1, "detail": 2, "pharma": 3}
        df["_parse_order"] = df["_ftype"].map(ftype_order).fillna(9)
        df = df.sort_values("_parse_order", kind="stable").drop(columns=["_parse_order"])

    disease_stats: dict = defaultdict(new_disease)
    basic_diagnosis_names: dict[str, str] = {}
    cross_day_index = defaultdict(lambda: {
        "max_basic_cost": 0,
        "basic_hospitals": set(),
        "detail_proc_names": set(),
        "has_detail_surg_kw": False,
        "has_detail_proc_kw": False,
        "inpatient_flag": False,
    })

    date_parse_fail_count = 0
    date_parse_fail_samples: list[str] = []
    future_date_count = 0

    # ── disease_stats 구축 루프 ───────────────────────────────────
    for _, row in df.iterrows():
        if row_is_junk(row):
            continue
        ftype    = str(row.get("_ftype", "unknown"))
        dept     = get_val(row, ["진단과"])

        if ftype in ("detail", "pharma"):
            raw_code = ""
        else:
            raw_code = get_diagnosis_code(row)
        code_str = normalize_code(raw_code)
        grouped_code_str = disclosure_group_code(code_str)

        if ftype == "detail":
            name_str = get_val(row, ["행위명칭", "행위명", "진료내역", "처치및수술", "처치및수 술"])
        elif ftype == "pharma":
            name_str = get_val(row, ["약품명", "의약품명"])
        else:
            name_str = get_diagnosis_name(row) or get_val(row, ["약품명", "진료내역",
                                                               "행위명칭", "행위명", "처치및수술", "처치및수 술"])

        in_out   = get_val(row, ["입내원구분", "입원외래구분", "입원", "외래", "구분"])
        hospital = get_val(row, ["병·의원", "기관명", "요양기관명"])
        date_str = get_val(row, ["진료개시일", "진료시작일", "진료일", "조제일자", "처방일"])
        m_days_raw = get_val(row, ["내원일수", "투약일수", "요양일수"])
        m_days = int(re.findall(r"\d+", m_days_raw)[0]) if re.findall(r"\d+", m_days_raw) else 0
        cost_raw = get_val(row, ["총진료비", "진료비", "총 진료비", "본인부담총액", "급여비용총액"])
        cost_val = _to_int_cost(cost_raw)

        if ftype in ("basic", "unknown") and dept.replace(" ", "") == "일반의" and not _keep_basic_general_row(code_str):
            continue

        if grouped_code_str:
            group_key = grouped_code_str
        elif ftype == "pharma":
            name_norm    = re.sub(r"[\s\d\.\-\[\]]", "", name_str)[:12]
            month_bucket = parse_date(date_str)[:7] if parse_date(date_str) else ""
            group_key = f"PHARMA|{name_norm}|{month_bucket}" if name_norm else ""
        else:
            group_key = ""
        if not group_key:
            continue

        clean_date = parse_date(date_str)
        if date_str and not clean_date:
            date_parse_fail_count += 1
            if len(date_parse_fail_samples) < 5:
                date_parse_fail_samples.append(date_str[:30])

        s = disease_stats[group_key]

        if grouped_code_str and ftype in ("basic", "unknown", "nhis"):
            diagnosis_name = get_diagnosis_name(row) or (name_str if ftype == "nhis" else "")
            diagnosis_name = disclosure_group_name(grouped_code_str, diagnosis_name)
            if diagnosis_name:
                basic_diagnosis_names.setdefault(grouped_code_str, diagnosis_name)

        if grouped_code_str and not s["diag_code"]:
            s["diag_code"] = grouped_code_str
        if grouped_code_str:
            canonical_name = basic_diagnosis_names.get(grouped_code_str) or disclosure_group_name(grouped_code_str, "")
            if canonical_name and (not s["name"] or s["name"] == grouped_code_str):
                s["name"] = canonical_name

        if clean_date:
            dt = datetime.strptime(clean_date, "%Y-%m-%d")
            days_ago = (today - dt).days

            if days_ago < 0:
                future_date_count += 1
                continue

            if ftype in ("basic", "unknown"):
                if "약국" in in_out:
                    continue
                is_inpatient = "입원" in in_out or "입원" in name_str
                if is_inpatient:
                    s["inpatient_dates"].add(clean_date)
                    if m_days > 0:
                        prev_inp = s["_inpatient_days_map"].get(clean_date, 0)
                        s["_inpatient_days_map"][clean_date] = max(prev_inp, m_days)
                        s.setdefault("inpatient_periods", []).append({
                            "start": clean_date,
                            "end": _add_days(clean_date, m_days),
                            "days": m_days,
                        })
                        if _add_days(clean_date, m_days) > s["latest_date"]:
                            s["latest_date"] = _add_days(clean_date, m_days)
                    elif clean_date not in s["_inpatient_days_map"]:
                        s["_inpatient_days_map"][clean_date] = 0
                else:
                    s["visit_dates"].add(clean_date)
                    s.setdefault("visit_events", []).append(clean_date)
                if m_days > 0:
                    prev = s["med_dates_basic"].get(clean_date, 0)
                    if m_days > prev:
                        s["med_dates_basic"][clean_date] = m_days
                if hospital and "약국" not in hospital:
                    s["hospital_dates"].setdefault(clean_date, hospital)
                day_fact = s["_daily_facts"].setdefault(clean_date, {"max_basic_cost": 0, "detail_proc_names": set()})
                day_fact["max_basic_cost"] = max(day_fact["max_basic_cost"], cost_val)
            elif ftype == "detail":
                act_name = get_val(row, ["행위명칭", "행위명", "진료내역", "처치"])
                surg_col = get_val(row, ["처치및수술", "처치및수 술", "처치/수술"])
                surg_target = act_name if act_name else name_str
                is_surg_by_column = bool(surg_col and surg_col.strip() and surg_col.strip() != "0")
                is_surg_by_keyword = _is_surgery_match(surg_target)

                if is_surg_by_column:
                    surg_label = surg_col.strip() if len(surg_col.strip()) > 2 else (surg_target or "처치및수술")
                    s["surgeries"].add(surg_label)
                    s["surgery_dates"].add(clean_date)
                elif is_surg_by_keyword:
                    s["surgeries"].add(surg_target)
                    s["surgery_dates"].add(clean_date)

                day_fact = s["_daily_facts"].setdefault(clean_date, {"max_basic_cost": 0, "detail_proc_names": set()})
                if surg_target:
                    day_fact["detail_proc_names"].add(surg_target)
                day_fact["_is_surg_by_column"] = day_fact.get("_is_surg_by_column", False) or is_surg_by_column
                for kw in test_keywords:
                    if kw in surg_target:
                        s["tests_found"].add(surg_target)
                        if clean_date and surg_target:
                            s.setdefault("test_events", []).append({
                                "date": clean_date,
                                "name": surg_target,
                                "hospital": hospital,
                                "source": "detail",
                            })
                        break
                _chk = act_name or name_str
                if "초진" in _chk:
                    s["chojin_count"] += 1
                elif "재진" in _chk:
                    s["jaejin_count"] += 1
            elif ftype == "pharma":
                _gubun = get_val(row, ["구분", "처방조제구분", "처방구분", "분류"])
                if _gubun and "조제" in _gubun and "처방" not in _gubun:
                    continue

                _target_groups = []
                for _ck, _cs in disease_stats.items():
                    if not _cs.get("diag_code") or _ck.startswith("PHARMA|"):
                        continue
                    if clean_date in _cs.get("visit_dates", set()) or \
                       clean_date in _cs.get("inpatient_dates", set()):
                        _target_groups.append(_ck)

                if _target_groups:
                    for _tg in _target_groups:
                        _ts = disease_stats[_tg]
                        _ts["has_pharma"] = True
                        if m_days > 0:
                            _prev = _ts["med_dates_pharma"].get(clean_date, 0)
                            if m_days > _prev:
                                _ts["med_dates_pharma"][clean_date] = m_days
                            _episode_key = hospital.strip() or "_unknown"
                            _episode_map = _ts.setdefault("med_dates_pharma_episode", {}).setdefault(clean_date, {})
                            _episode_map[_episode_key] = max(_episode_map.get(_episode_key, 0), m_days)
                        _drug = name_str.strip()
                        if _drug:
                            if days_ago <= 90:
                                _ts["drug_names_in_90"].add(_drug)
                            else:
                                _ts["drug_names_before_90"].add(_drug)
                    continue

                s["has_pharma"] = True
                if m_days > 0:
                    prev = s["med_dates_pharma"].get(clean_date, 0)
                    if m_days > prev:
                        s["med_dates_pharma"][clean_date] = m_days
                    _episode_key = hospital.strip() or "_unknown"
                    _episode_map = s.setdefault("med_dates_pharma_episode", {}).setdefault(clean_date, {})
                    _episode_map[_episode_key] = max(_episode_map.get(_episode_key, 0), m_days)
                drug = name_str.strip()
                if drug:
                    if days_ago <= 90: s["drug_names_in_90"].add(drug)
                    else: s["drug_names_before_90"].add(drug)
            elif ftype == "nhis":
                if in_out == "입원":
                    s["inpatient_dates"].add(clean_date)
                    if m_days > 0:
                        prev_inp = s["_inpatient_days_map"].get(clean_date, 0)
                        s["_inpatient_days_map"][clean_date] = max(prev_inp, m_days)
                        s.setdefault("inpatient_periods", []).append({
                            "start": clean_date,
                            "end": _add_days(clean_date, m_days),
                            "days": m_days,
                        })
                        if _add_days(clean_date, m_days) > s["latest_date"]:
                            s["latest_date"] = _add_days(clean_date, m_days)
                elif in_out == "약국":
                    s["has_pharma"] = True
                else:
                    s["visit_dates"].add(clean_date)
                    s.setdefault("visit_events", []).append(clean_date)
                if _is_surgery_match(name_str) or any(kw in name_str for kw in nhis_surg_keywords):
                    s["surgeries"].add(name_str)
                    if clean_date: s["surgery_dates"].add(clean_date)
                for kw in test_keywords:
                    if kw in name_str: s["tests_found"].add(name_str); break

            if ftype in ("basic", "unknown"):
                if _is_surgery_match(name_str):
                    s["surgeries"].add(name_str)
                    if clean_date: s["surgery_dates"].add(clean_date)
                for kw in test_keywords:
                    if kw in name_str: s["tests_found"].add(name_str); break

            if clean_date > s["latest_date"]: s["latest_date"] = clean_date
            if clean_date < s["first_date"]:  s["first_date"]  = clean_date

            ckey = _cross_key(code_str, name_str)
            if ckey:
                idx = cross_day_index[(ckey, clean_date)]
                if ftype in ("basic", "unknown"):
                    idx["max_basic_cost"] = max(idx["max_basic_cost"], cost_val)
                    if hospital:
                        idx["basic_hospitals"].add(hospital)
                    if "입원" in in_out or "입원" in name_str:
                        idx["inpatient_flag"] = True
                elif ftype == "detail":
                    act_name_idx = get_val(row, ["행위명칭", "행위명", "진료내역", "처치", "처치및수술", "처치및수 술"])
                    target_idx = act_name_idx if act_name_idx else name_str
                    if target_idx:
                        idx["detail_proc_names"].add(target_idx)
                    if _is_surgery_match(target_idx):
                        idx["has_detail_surg_kw"] = True
                    if _is_procedure_kw(target_idx):
                        idx["has_detail_proc_kw"] = True

        if hospital and "약국" not in hospital and ftype != "pharma":
            s["hospitals"].add(hospital)
        if name_str and ftype not in ("detail", "pharma"):
            canonical_name = basic_diagnosis_names.get(grouped_code_str) or disclosure_group_name(code_str, _clean_disease_name(name_str))
            if canonical_name and (not s["name"] or s["name"] == grouped_code_str):
                s["name"] = canonical_name

    # ── 기본/세부 동일일자 교차 수술/시술 판정 ────────────────────
    cross_surgery_hints: list[str] = []
    for _ck, _s in disease_stats.items():
        _dc = (_s.get("diag_code") or "").strip()
        _name = _s.get("name", "")
        ckey = _cross_key(_dc, _name) if (_dc or _name) else ""
        if not ckey:
            continue
        for d, day_fact in _s.get("_daily_facts", {}).items():
            idx = cross_day_index.get((ckey, d))
            if not idx:
                continue
            max_cost = idx.get("max_basic_cost", 0)
            has_detail_proc    = bool(idx.get("detail_proc_names"))
            has_detail_surg_kw = bool(idx.get("has_detail_surg_kw"))
            has_detail_proc_kw = bool(idx.get("has_detail_proc_kw"))
            is_col_confirmed   = day_fact.get("_is_surg_by_column", False)

            if is_col_confirmed:
                if d not in _s["surgery_dates"]:
                    _s["surgery_dates"].add(d)
                    if idx["detail_proc_names"]:
                        _s["surgeries"].update(idx["detail_proc_names"])
                cross_surgery_hints.append(
                    f"{d} {_dc or ckey} {'|'.join(_sorted_strings(idx.get('detail_proc_names', set()))[:2]) or _name} "
                    f"컬럼확정(처치및수술+기본진료비 {max_cost:,}원)"
                )
            elif max_cost >= SURGERY_COST_THRESHOLD:
                if has_detail_surg_kw:
                    if d not in _s["surgery_dates"]:
                        _s["surgery_dates"].add(d)
                    if idx["detail_proc_names"]:
                        for pn in idx["detail_proc_names"]:
                            if _is_confirmed_surgery_cost_kw(pn) or _is_surgery_match(pn):
                                _s["surgeries"].add(pn)
                        if not (_s["surgeries"] & set(idx["detail_proc_names"])):
                            _s["surgeries"].update(idx["detail_proc_names"])
                        _hint_name = next(iter(_sorted_strings(idx["detail_proc_names"])))
                    else:
                        _hint_name = _name or _dc or "수술"
                    cross_surgery_hints.append(
                        f"{d} {_dc or ckey} {_hint_name} 교차확정(수술키워드+기본진료비 {max_cost:,}원)"
                    )
                elif has_detail_proc:
                    _hint_name = next(iter(_sorted_strings(idx["detail_proc_names"])), _name or "수술 의심")
                    _s["surgery_suspected_names"].add(_hint_name)
                    _s["surgery_suspected_dates"].add(d)
                    cross_surgery_hints.append(
                        f"{d} {_dc or ckey} {_hint_name} 수술의심(키워드없음+기본진료비 {max_cost:,}원) ★설계사확인"
                    )
            elif max_cost >= PROCEDURE_COST_THRESHOLD:
                if has_detail_proc_kw:
                    for pn in (idx.get("detail_proc_names") or set()):
                        if _is_procedure_kw(pn):
                            _s["procedures"].add(pn)
                    _s["procedure_dates"].add(d)
                elif has_detail_surg_kw:
                    _hint_name = next(iter(_sorted_strings(idx["detail_proc_names"]))) if idx["detail_proc_names"] else (_name or _dc or "진료")
                    cross_surgery_hints.append(
                        f"{d} {_dc or ckey} {_hint_name} 교차후보(수술키워드+기본진료비 {max_cost:,}원) ★AI판단필요"
                    )

    # ── 날짜 파싱 실패/미래일자 경고 ─────────────────────────────
    date_warnings: list[str] = []
    if date_parse_fail_count > 0:
        sample_text = ", ".join(date_parse_fail_samples[:3])
        date_warnings.append(
            f"⚠️ 날짜 인식 실패 {date_parse_fail_count}건 (예: {sample_text}) — "
            f"해당 레코드의 기간 판정이 누락될 수 있습니다."
        )
    if future_date_count > 0:
        date_warnings.append(
            f"⚠️ 미래 날짜 {future_date_count}건 감지 (OCR 오류 가능) — 해당 레코드를 제외했습니다."
        )

    # ── AI 전달용 raw_entries 빌드 (같은 df 재사용) ──────────────
    raw_entries: list[tuple[str, str]] = []
    seen_code_dates: set = set()
    _d10y_dt = today - __import__("datetime").timedelta(days=3650)

    for _, row in df.iterrows():
        if row_is_junk(row): continue
        ftype    = str(row.get("_ftype", ""))
        dept     = get_val(row, ["진단과"])
        if ftype in ("basic", "unknown") and dept.replace(" ", "") == "일반의":
            continue
        date_str = get_val(row, ["진료개시일", "진료시작일", "진료일", "조제일자", "처방일"])
        code_raw = "" if ftype in ("detail", "pharma") else get_diagnosis_code(row)
        code_str = normalize_code(code_raw)
        if ftype == "detail":
            name_str = get_val(row, ["행위명칭", "행위명", "진료내역", "처치및수술"])
        elif ftype == "pharma":
            name_str = get_val(row, ["약품명", "의약품명"])
        else:
            name_str = (
                get_diagnosis_name(row)
                or get_val(row, ["진료내역", "행위명"])
            )
        hospital = get_val(row, ["병·의원", "기관명", "요양기관명"])
        in_out   = get_val(row, ["입내원구분", "입원외래구분", "입원", "외래", "구분"])
        m_days   = get_val(row, ["내원일수", "투약일수", "요양일수"])
        cost_raw = get_val(row, ["총진료비", "진료비", "총 진료비"])

        if not date_str and not name_str: continue
        if ftype == "pharma" and not m_days: continue

        if ftype == "detail":
            act_name_raw = get_val(row, ["행위명칭", "행위명", "진료내역", "처치"])
            display_name = name_str[:20]
            act_norm = re.sub(r"[\s\d]", "", (act_name_raw or ""))[:15]
            dedup_key = (code_str, date_str, ftype, act_norm)
        else:
            display_name = name_str[:20]
            name_norm_dedup = re.sub(r"[\s\d]", "", name_str)[:15]
            dedup_key = (code_str or name_norm_dedup, date_str, ftype, "")
        if dedup_key in seen_code_dates:
            continue
        seen_code_dates.add(dedup_key)

        fname_row = str(row.get("_fname", "") or "")
        inpatient_flag = "입원" if "입원" in in_out else ""
        line_date = parse_date(date_str) or date_str

        act_suffix = ""
        if ftype == "detail":
            _act = get_val(row, ["행위명칭", "행위명", "진료내역", "처치"])
            if _act:
                act_suffix = f" 행위:{_act[:25]}"
        line_core = (
            f"{line_date} [{ftype}] {code_str} {display_name}{act_suffix} {hospital[:10]}"
            + (f" 투약{m_days}일" if m_days and m_days != "0" else "")
            + (f" 진료비{cost_raw}" if cost_raw else "")
            + (f" {inpatient_flag}" if inpatient_flag else "")
        )
        raw_entries.append((fname_row, line_core))

    del df
    gc.collect()

    lines_by_file: dict[str, list[str]] = defaultdict(list)
    for fname_row, tl in raw_entries:
        if fname_row:
            lines_by_file[fname_row].append(tl)

    return disease_stats, cross_surgery_hints, date_warnings, raw_entries, dict(lines_by_file)


def detect_drug_changes(disease_stats: dict, today: datetime) -> list[dict]:
    """3개월 이내 처방약 변경 감지."""
    drug_change_summary: list[dict] = []

    for group_key, s in disease_stats.items():
        drugs_in_90     = s.get("drug_names_in_90", set())
        drugs_before_90 = s.get("drug_names_before_90", set())
        if not drugs_in_90 or not drugs_before_90:
            continue

        info_in_90     = {extract_drug_info(d)[0]: extract_drug_info(d)[1] for d in drugs_in_90}
        info_before_90 = {extract_drug_info(d)[0]: extract_drug_info(d)[1] for d in drugs_before_90}
        norm_in_90     = set(info_in_90.keys())
        norm_before_90 = set(info_before_90.keys())

        stopped_drugs   = norm_before_90 - norm_in_90
        new_drugs       = norm_in_90 - norm_before_90
        continued_drugs = norm_in_90 & norm_before_90

        dose_increased = []
        dose_decreased = []
        for drug_name in continued_drugs:
            dose_before = info_before_90.get(drug_name, 0)
            dose_after  = info_in_90.get(drug_name, 0)
            if dose_before > 0 and dose_after > 0:
                if dose_after > dose_before:
                    dose_increased.append(f"{drug_name} ({dose_before}→{dose_after})")
                elif dose_after < dose_before:
                    dose_decreased.append(f"{drug_name} ({dose_before}→{dose_after})")

        has_change = bool(new_drugs or dose_increased)
        if has_change or stopped_drugs:
            if new_drugs and stopped_drugs:
                change_type = "약 종류 변경"
            elif new_drugs:
                change_type = "새 약 추가"
            elif dose_increased:
                change_type = "용량 증가"
            else:
                change_type = "약 중단"

            if new_drugs or dose_increased:
                drug_change_summary.append({
                    "group":          group_key,
                    "name":           s.get("name", group_key),
                    "continued":      sorted(continued_drugs)[:3],
                    "stopped":        sorted(stopped_drugs)[:3],
                    "new":            sorted(new_drugs)[:3],
                    "dose_increased": sorted(dose_increased)[:3],
                    "dose_decreased": sorted(dose_decreased)[:3],
                    "change_type":    change_type,
                })
                disease_stats[group_key]["drug_change_in_3m"] = True

    return drug_change_summary


def compute_prescription_end_dates(
    disease_stats: dict,
    today: datetime,
) -> tuple[list[dict], datetime | None]:
    """3개월 이내 처방 종료일 계산.

    Returns:
        prescription_end_details : list[dict]
        earliest_available_date  : datetime | None
    """
    earliest_available_date = None
    prescription_end_details: list[dict] = []

    for group_key, s in disease_stats.items():
        med_dict = s["med_dates_pharma"] if s["has_pharma"] and s["med_dates_pharma"] else s["med_dates_basic"]
        if not med_dict:
            continue
        for presc_date_str, m_days_val in med_dict.items():
            if not presc_date_str or m_days_val <= 0:
                continue
            try:
                presc_dt = datetime.strptime(presc_date_str, "%Y-%m-%d")
            except ValueError:
                continue
            days_ago = (today - presc_dt).days
            if days_ago > 90:
                continue
            end_dt       = presc_dt + timedelta(days=m_days_val - 1)
            available_dt = end_dt + timedelta(days=1)
            prescription_end_details.append({
                "name":       s.get("name", group_key),
                "presc_date": presc_date_str,
                "m_days":     m_days_val,
                "end_date":   end_dt.strftime("%Y-%m-%d"),
                "available":  available_dt.strftime("%Y-%m-%d"),
                "already_ok": available_dt <= today,
            })
            if earliest_available_date is None or available_dt > earliest_available_date:
                earliest_available_date = available_dt

    return prescription_end_details, earliest_available_date
