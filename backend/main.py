import asyncio
import logging
import os
import re
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from fastapi import FastAPI, File, Request, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from analyzer import run_analysis, AnalysisError

# ── 서비스 환경 ──────────────────────────────────────────────────────────────
SENTRY_DSN  = os.environ.get("SENTRY_DSN", "")
SERVICE_ENV = os.environ.get("SERVICE_ENV", "development")


def _sanitize_event(event, hint=None):
    """Sentry 전송 전 PDF 바이너리·진료 데이터·이메일 등 민감정보 제거"""
    try:
        req = event.get("request") or {}
        req.pop("data", None)
        req.pop("cookies", None)
        headers = req.get("headers") or {}
        for k in list(headers.keys()):
            if k.lower() in ("authorization", "cookie", "x-api-key"):
                headers[k] = "[Filtered]"
        for ctx in (event.get("contexts") or {}).values():
            if isinstance(ctx, dict):
                for big in ("raw_response", "parsed_records", "summary_reports"):
                    ctx.pop(big, None)
    except Exception:
        pass
    return event


if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SERVICE_ENV,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        before_send=_sanitize_event,
    )

# ── FastAPI 앱 ───────────────────────────────────────────────────────────────
app = FastAPI(title="SURIT React Backend", version="1.0.0")

# ── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ─────────────────────────────────────────────────────────────────────
_default_origins = "https://surit-react.vercel.app,http://localhost:5173,http://localhost:3000"
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── 로깅 설정 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("surit")
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# ── 상수 ─────────────────────────────────────────────────────────────────────
PRODUCT_TYPE_MAP = {
    "standard": "건강체/표준체 (일반심사)",
    "easy":     "간편심사 (유병자 3-5-5 기준)",
}


# ── 내부 유틸 ────────────────────────────────────────────────────────────────
class _PDFFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def read(self) -> bytes:
        return self._data


def _s(v) -> str:
    """None-safe 문자열 변환: None이면 "" 반환, 그 외 str()."""
    return "" if v is None else str(v)


def _kakao_item(item: dict) -> str:
    fd = _s(item.get("first_date"))
    ld = _s(item.get("latest_date"))
    date_str = f"{fd} ~ {ld}" if fd and ld and fd != ld else (fd or ld or "")

    code_clean = _s(item.get("display_code") or item.get("code"))
    raw_hospitals = item.get("hospitals") or []
    hosp_list = [_s(h) for h in (raw_hospitals if isinstance(raw_hospitals, list) else list(raw_hospitals))]
    hosp_str = ", ".join(hosp_list)
    kind = "(한방)" if any(k in hosp_str for k in ["한의원", "한방", "한의"]) else "(양방)"

    inpatient = item.get("inpatient") or 0
    if inpatient > 0:
        visit_str = f"입원{inpatient}일"
    else:
        visit_str = f"통원{item.get('visit') or 1}회"

    line1 = f"{date_str} / {visit_str} / {code_clean} / {kind}{_s(item.get('name'))}\n"

    surgeries = item.get("surgeries") or []
    if surgeries:
        surg_names = [s for s in surgeries if s and s != "수술"]
        line2 = (", ".join(surg_names) if surg_names else "수술") + "\n"
    else:
        detail = _s(item.get("detail"))
        line2 = f"{detail[:60]}\n" if detail else ""

    return line1 + line2 + "\n"


def _build_kakao_message(product_type_kr: str, today, summary_reports: dict) -> str:
    msg = f"[{_s(product_type_kr)} 고지 사항]\n"
    msg += f"기준일: {today.strftime('%Y-%m-%d')}\n\n"

    if not summary_reports:
        msg += "고지 대상 없음\n"
        return msg

    def _q_sort_key(title):
        m = re.search(r'\d+', _s(title))
        return int(m.group()) if m else 999

    for q_title in sorted(summary_reports.keys(), key=_q_sort_key):
        clean_title = re.sub(r"^\[.*?\]\s*", "", _s(q_title))
        msg += f"> {clean_title}\n"
        items_q = summary_reports.get(q_title) or []
        inpatient_items = [i for i in items_q if (i.get("inpatient") or 0) > 0]
        surgery_items   = [i for i in items_q if not (i.get("inpatient") or 0) > 0 and i.get("surgeries")]
        other_items     = [i for i in items_q if not (i.get("inpatient") or 0) > 0 and not i.get("surgeries")]

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
    def _q_sort_key(title):
        m = re.search(r'\d+', title)
        return int(m.group()) if m else 999

    def _to_list(v):
        if isinstance(v, set):
            return sorted(v)
        return v if v is not None else []

    out = {}
    for q_title in sorted(summary_reports.keys(), key=_q_sort_key):
        items = summary_reports[q_title]
        out[q_title] = [
            {
                **item,
                "surgeries":         _to_list(item.get("surgeries")),
                "procedures":        _to_list(item.get("procedures")),
                "surgery_suspected": _to_list(item.get("surgery_suspected")),
                "additional_tests":  _to_list(item.get("additional_tests")),
                "inpatient_periods": _to_list(item.get("inpatient_periods")),
            }
            for item in items
        ]
    return out


# ── 엔드포인트 ───────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    google_key_ok = bool(os.environ.get("GOOGLE_API_KEY"))
    return {
        "status": "ok",
        "env": SERVICE_ENV,
        "deps": {
            "google_api_key": google_key_ok,
            "sentry": bool(SENTRY_DSN),
        },
        "version": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:7],
    }


@app.post("/api/analyze")
@limiter.limit("5/minute,30/hour")
async def analyze(
    request: Request,
    files: list[UploadFile] = File(..., description="심평원 진료 PDF"),
    reference_date: str = Form(..., description="YYYY-MM-DD"),
    birthdate_pw: str = Form(default="", description="PDF 비밀번호용 생년월일"),
):
    try:
        ref_date = date.fromisoformat(reference_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="reference_date는 YYYY-MM-DD 형식이어야 합니다.")

    if not files:
        raise HTTPException(status_code=400, detail="PDF 파일을 1개 이상 업로드해 주세요.")

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="서비스 점검 중입니다. 잠시 후 다시 시도해 주세요.",
        )

    logger.info(
        "analyze start: ref_date=%s files=%d",
        reference_date, len(files),
    )

    async def _read(f):
        data = await f.read()
        return _PDFFile(name=f.filename or "unknown.pdf", data=data)

    active_files = await asyncio.gather(*[_read(f) for f in files])

    # 표준 컨텍스트로 AI 분석 (Q1-Q4 전체 수집) — 간편 결과는 파생
    product_type_kr = PRODUCT_TYPE_MAP["standard"]

    try:
        result = await run_analysis(
            active_files=active_files,
            product_type=product_type_kr,
            reference_date=ref_date,
            birthdate_pw=birthdate_pw,
            api_key=api_key,
        )
    except AnalysisError as e:
        # 사용자 친화 메시지 그대로 전달 (parse_single_pdf 에서 이미 정제됨)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 내부 오류는 사용자에게 디테일 노출 금지. 서버 로그·Sentry 에는 남김.
        logger.exception("analyze endpoint failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="서버에서 분석을 완료하지 못했어요. 잠시 후 다시 시도해 주세요.",
        )

    std_reports   = result["standard_reports"]
    easy_reports  = result["easy_reports"]
    flagged_codes = result["flagged_codes"]
    today         = result["analysis_today"]
    ai_res        = result["ai_result"]
    meritz        = result.get("meritz_easy", {})

    logger.info(
        "analyze done: flagged=%d total_q=%d",
        len(flagged_codes), len(std_reports),
    )

    std_kakao  = _build_kakao_message(PRODUCT_TYPE_MAP["standard"], today, std_reports)
    easy_kakao = _build_kakao_message(PRODUCT_TYPE_MAP["easy"],     today, easy_reports)
    if meritz.get("detail_message"):
        std_kakao  += "\n" + meritz["detail_message"]
        easy_kakao += "\n" + meritz["detail_message"]

    return {
        "flagged_count":        len(flagged_codes),
        "total_q_count":        len(std_reports),
        "total_visit_sum":      sum(item["visit"] for items in std_reports.values() for item in items),
        "total_med_sum":        sum(item["med_days"] for items in std_reports.values() for item in items),
        "standard_reports":     _serialize_reports(std_reports),
        "easy_reports":         _serialize_reports(easy_reports),
        "all_disease_summary":  result["all_disease_summary"],
        "standard_kakao":       std_kakao,
        "easy_kakao":           easy_kakao,
        "kakao_message":        std_kakao,   # 하위 호환
        "parse_errors":         result["parse_errors"],
        "warnings":             result["retry_warnings"],
        "verdict":              ai_res.get("health_verdict") or ai_res.get("simple_verdict", ""),
        "verdict_reason":       ai_res.get("health_reason") or ai_res.get("simple_reason", ""),
        "recommend":            ai_res.get("recommend", ""),
        "meritz_easy_eligible":         meritz.get("meritz_easy_eligible", False),
        "meritz_easy_exception_count":  meritz.get("exception_diseases_count", 0),
        "meritz_easy_recommended_year": meritz.get("recommended_disclosure_year"),
        "meritz_easy_details":          meritz.get("exception_diseases", []) + meritz.get("rejected_diseases", []),
        "meritz_easy_message":          meritz.get("detail_message", ""),
    }
