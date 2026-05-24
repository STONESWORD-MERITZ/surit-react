"""PDF 파싱 — analyzer.py 에서 이동."""
from __future__ import annotations

import functools
import gc
import io
import re

import pdfplumber

from .helpers import (
    _FTYPE_KW,
    AnalysisError,
    _is_surgery_match,
    get_val,
    normalize_code,
    parse_date,
    row_is_junk,
    nhis_surg_keywords,
    test_keywords,
)


@functools.lru_cache(maxsize=512)
def detect_file_type(headers):
    h_joined = " ".join(str(h) for h in headers)
    h_norm = h_joined.replace(" ", "").replace("\n", "")

    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["pharma"]):
        return "pharma"
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["detail"]):
        return "detail"
    if any(k in h_joined or k in h_norm for k in _FTYPE_KW["basic"]):
        return "basic"

    n_cols = len(headers)
    has_date_col = any(re.search(r"일$|날짜|일자|개시", str(h)) for h in headers)
    has_code_like = any(re.search(r"코드|기호|분류", str(h)) for h in headers)
    has_drug_like = any(re.search(r"약|처방|조제|투약", str(h)) for h in headers)
    has_act_like = any(re.search(r"행위|내역|명칭|처치|급여", str(h)) for h in headers)

    if has_drug_like:
        return "pharma"
    if has_act_like and n_cols >= 5:
        return "detail"
    if has_date_col and has_code_like:
        return "basic"

    return "unknown"


def _detect_ftype_by_page_text(text: str) -> str:
    if not text:
        return ""
    if "기본진료정보" in text:
        return "basic"
    if "세부진료정보" in text:
        return "detail"
    if "처방조제" in text:
        return "pharma"
    return ""


def _open_pdf(data, bdate_str):
    bd = (bdate_str or "").strip()
    bd_digits = re.sub(r"\D", "", bd)
    candidates = [""]
    if bd:
        candidates.append(bd)
    if bd_digits and bd_digits != bd:
        candidates.append(bd_digits)
    if len(bd_digits) == 8:
        candidates.append(bd_digits[2:])
    elif len(bd_digits) == 6:
        yy = int(bd_digits[:2])
        prefix = "20" if yy <= 24 else "19"
        candidates.append(prefix + bd_digits)
    candidates = list(dict.fromkeys(candidates))
    for pw in candidates:
        try:
            return pdfplumber.open(io.BytesIO(data), password=pw)
        except Exception:
            continue
    raise ValueError("PDF 비밀번호 해제 실패 — 생년월일을 확인해 주세요.")


def parse_nhis_text(text, fname):
    records = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    date_re  = re.compile(r'^(\d{4}\.\d{2}\.\d{2})\s+\d+\s+(.+?)\s+\d{2,4}-\d{3,4}-\d{4}')
    visit_re = re.compile(r'^(외래|입원|약국)\s+(\d+)\s*(.*)')
    seq_re   = re.compile(r'^\d+$')
    cur_date, cur_hospital = None, None
    i = 0
    while i < len(lines):
        line = lines[i]
        m_d = date_re.match(line)
        if m_d:
            cur_date     = m_d.group(1)
            cur_hospital = m_d.group(2).strip()
            i += 1
            continue
        if seq_re.match(line) and cur_date:
            i += 1
            if i < len(lines):
                m_v = visit_re.match(lines[i])
                if m_v:
                    in_out_v = m_v.group(1)
                    if in_out_v == "약국":
                        i += 1
                        continue
                    days_v = m_v.group(2)
                    rest   = m_v.group(3).strip()
                    parts  = rest.split()
                    code_v = ""
                    name_v = ""
                    for pi, p in enumerate(parts):
                        if re.match(r'^[A-Z]\d', p):
                            code_v = p
                            name_v = " ".join(parts[:pi])
                            break
                    if not name_v and not code_v:
                        name_v = rest
                    if name_v or code_v:
                        records.append({
                            "진료개시일": cur_date,
                            "요양기관명": cur_hospital or "",
                            "입내원구분": in_out_v,
                            "요양일수":   days_v,
                            "상병명":     name_v,
                            "상병코드":   code_v,
                            "_ftype":     "nhis",
                            "_fname":     fname,
                        })
                i += 1
            continue
        i += 1
    return records


def _empty_result_message(fname: str, n_pages: int, first_text: str) -> str:
    """PDF가 정상적으로 열렸으나 진료 레코드가 0건일 때 원인별 안내.

    비밀번호 문제로 오인되지 않도록 '비밀번호'를 언급하지 않는다.
    """
    if n_pages == 0:
        return f"⚠️ {fname}: 페이지가 없는 빈 PDF입니다."
    if not (first_text or "").strip():
        return (
            f"🖼️ {fname}: 이미지로만 구성된 PDF로 보입니다 (텍스트 인식 불가). "
            f"심평원에서 '파일'로 직접 내려받은 PDF를 사용해 주세요 — "
            f"스캔본·사진·캡처본은 분석할 수 없습니다."
        )
    return (
        f"⚠️ {fname}: PDF는 열렸으나 인식 가능한 진료 표를 찾지 못했습니다. "
        f"심평원 '진료받은내역' 또는 '건강보험 요양급여내역' PDF가 맞는지 확인해 주세요."
    )


def parse_single_pdf(uploaded_file, birthdate_pw) -> dict:
    """PDF 1개 파싱. pdfplumber 동기 I/O."""
    fname = getattr(uploaded_file, "name", None) or getattr(uploaded_file, "filename", None) or "unknown.pdf"
    file_recs: list = []
    parse_errors_local: list = []
    pdf_data = uploaded_file.read()
    try:
        with _open_pdf(pdf_data, birthdate_pw or "") as pdf:
            first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
            is_nhis = "건강보험 요양급여내역" in first_text
            page_ftype = _detect_ftype_by_page_text(first_text)

            if is_nhis:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if "건강보험 요양급여내역" in page_text:
                        recs = parse_nhis_text(page_text, fname)
                        file_recs.extend(recs)
                    del page_text
            else:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        raw_headers = table[0]
                        headers = [
                            str(h).replace("\n", "").replace(" ", "") if h else f"col_{i}"
                            for i, h in enumerate(raw_headers)
                        ]
                        header_ftype = detect_file_type(tuple(headers))
                        ftype = header_ftype if header_ftype != "unknown" else (page_ftype or "unknown")
                        for row in table[1:]:
                            if not any(row):
                                continue
                            if "순번" in str(row[0]):
                                continue
                            rec = {h: str(v).replace("\n", " ").strip() if v else "" for h, v in zip(headers, row)}
                            rec["_ftype"] = ftype
                            rec["_fname"] = fname
                            file_recs.append(rec)
                    del tables

            if not file_recs:
                parse_errors_local.append(
                    _empty_result_message(fname, len(pdf.pages), first_text)
                )
    except ValueError as e:
        parse_errors_local.append(f"🔒 {fname}: {e}")
    except Exception as e:
        err_str = str(e)
        if "password" in err_str.lower() or "encrypted" in err_str.lower():
            parse_errors_local.append(f"🔒 {fname}: 비밀번호가 걸린 PDF입니다. 생년월일을 입력해 주세요.")
        elif "pdf" in err_str.lower() or "syntax" in err_str.lower():
            parse_errors_local.append(f"⚠️ {fname}: 손상되었거나 지원하지 않는 PDF 형식입니다.")
        else:
            parse_errors_local.append(f"⚠️ {fname}: 파일 읽기 실패 — {err_str[:80]}")
    finally:
        del pdf_data
        gc.collect()
    return {"filename": fname, "records": file_recs, "parse_errors": parse_errors_local}
