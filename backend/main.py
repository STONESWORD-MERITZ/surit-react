import sys
import os
import re
from pathlib import Path
from datetime import date

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# surit/analyzer.py 참조
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "surit"))

from analyzer import run_analysis, AnalysisError  # noqa: E402

app = FastAPI(title="SURIT React Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PRODUCT_TYPE_MAP = {
    "standard": "건강체/표준체 (일반심사)",
    "easy":     "간편심사 (유병자 3-5-5 기준)",
}


class _PDFFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def read(self) -> bytes:
        return self._data


def _kakao_item(item: dict) -> str:
    fd = item["first_date"]
    ld = item["latest_date"]
    date_str = f"{fd} ~ {ld}" if fd and ld and fd != ld else (fd or ld or "")

    code_clean = item["code"].replace(".", "")
    hosp_list = item["hospitals"] if isinstance(item["hospitals"], list) else list(item["hospitals"])
    hosp_str = ", ".join(hosp_list)
    kind = "(한방)" if any(k in hosp_str for k in ["한의원", "한방", "한의"]) else "(양방)"

    if item["inpatient"] > 0:
        visit_str = f"입원{item['inpatient']}일"
    else:
        visit_str = f"통원{item.get('visit', 1) or 1}회"

    line1 = f"{date_str} / {visit_str} / {code_clean} / {kind}{item['name']}\n"

    if item["surgeries"]:
        surg_names = [s for s in item["surgeries"] if s and s != "수술"]
        line2 = (", ".join(surg_names) if surg_names else "수술") + "\n"
    else:
        detail_short = item["detail"][:60] if item["detail"] else ""
        line2 = f"{detail_short}\n" if detail_short else ""

    return line1 + line2 + "\n"


def _build_kakao_message(product_type_kr: str, today, summary_reports: dict) -> str:
    msg = f"[{product_type_kr} 고지 사항]\n"
    msg += f"기준일: {today.strftime('%Y-%m-%d')}\n\n"

    if not summary_reports:
        msg += "고지 대상 없음\n"
        return msg

    for q_title in sorted(summary_reports.keys()):
        clean_title = re.sub(r"^\[.*?\]\s*", "", q_title)
        msg += f"> {clean_title}\n"
        items_q = summary_reports[q_title]
        inpatient_items = [i for i in items_q if i["inpatient"] > 0]
        surgery_items = [i for i in items_q if not i["inpatient"] > 0 and i["surgeries"]]
        other_items = [i for i in items_q if not i["inpatient"] > 0 and not i["surgeries"]]

        if inpatient_items:
            msg += "[입원]\n"
            for item in inpatient_items:
                msg += _kakao_item(item)
        if surgery_items:
            msg += "[수술]\n"
            for item in surgery_items:
                msg += _kakao_item(item)
        if other_items:
            msg += "[통원]\n"
            for item in other_items:
                msg += _kakao_item(item)
        msg += "\n"

    return msg


def _serialize_reports(summary_reports: dict) -> dict:
    out = {}
    for q_title, items in summary_reports.items():
        out[q_title] = [
            {
                **item,
                "surgeries": list(item["surgeries"])
                             if isinstance(item["surgeries"], set)
                             else item["surgeries"],
            }
            for item in items
        ]
    return out


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(
    files: list[UploadFile] = File(..., description="심평원 진료 PDF"),
    product_type: str = Form(..., description="'standard' 또는 'easy'"),
    reference_date: str = Form(..., description="YYYY-MM-DD"),
    birthdate_pw: str = Form(default="", description="PDF 비밀번호용 생년월일"),
):
    product_type_kr = PRODUCT_TYPE_MAP.get(product_type)
    if not product_type_kr:
        raise HTTPException(status_code=400, detail=f"product_type은 'standard' 또는 'easy'여야 합니다.")

    try:
        ref_date = date.fromisoformat(reference_date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"reference_date는 YYYY-MM-DD 형식이어야 합니다.")

    if not files:
        raise HTTPException(status_code=400, detail="PDF 파일을 1개 이상 업로드해 주세요.")

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="서버에 GOOGLE_API_KEY가 설정되지 않았습니다.")

    active_files = []
    for f in files:
        data = await f.read()
        active_files.append(_PDFFile(name=f.filename or "unknown.pdf", data=data))

    try:
        result = run_analysis(
            active_files=active_files,
            product_type=product_type_kr,
            reference_date=ref_date,
            birthdate_pw=birthdate_pw,
            api_key=api_key,
        )
    except AnalysisError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 중 오류: {e}")

    summary_reports = result["summary_reports"]
    flagged_codes = result["flagged_codes"]
    today = result["analysis_today"]

    return {
        "flagged_count":   len(flagged_codes),
        "total_q_count":   len(summary_reports),
        "total_visit_sum": sum(item["visit"] for items in summary_reports.values() for item in items),
        "total_med_sum":   sum(item["med_days"] for items in summary_reports.values() for item in items),
        "summary_reports": _serialize_reports(summary_reports),
        "kakao_message":   _build_kakao_message(product_type_kr, today, summary_reports),
        "parse_errors":    result["parse_errors"],
        "warnings":        result["retry_warnings"],
    }
