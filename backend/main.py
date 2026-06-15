import time
import logging
import traceback                                          # 추가
from fastapi import FastAPI, Request, HTTPException       # HTTPException 추가
from fastapi.exceptions import RequestValidationError     # 추가
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse                # 추가
from backend.api import chat, policies, conditions


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="청년 정책 통합 탐색 에이전트 API",
    description=(
        "SK네트웍스 Family AI 캠프 29기 | 청년 정책 RAG 에이전트 백엔드\n\n"
        "자연어 질문으로 청년 정책, 창업공고, 교육훈련을 통합 검색하고 "
        "자격 가능성과 신청 안내를 제공합니다."
    ),
    version="1.0.0",
    contact={
        "name": "SKN 29기 팀",
        "url": "https://github.com/idenist/SKN29-3rd-5TEAM",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(policies.router, prefix="/api")
app.include_router(conditions.router, prefix="/api")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.2f}s)")
    return response

# ── exception_handler 3종 추가 ────────────────────────────

# 1. Pydantic 요청 유효성 오류 → 422
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"[422] 요청 유효성 오류 {request.url.path} | {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "요청 형식이 올바르지 않습니다.",
            "errors": exc.errors(),
        },
    )

# 2. 명시적 HTTPException → 그대로 반환 + 로깅
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"[{exc.status_code}] {request.url.path} | {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

# 3. 예상 못한 모든 예외 → 500
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"[500] 미처리 예외 {request.url.path}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."},
    )


@app.get("/", tags=["Root"])
def root():
    return {"message": "청년 정책 RAG 에이전트 API 서버입니다. /docs 에서 API 명세를 확인하세요."}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "youth-policy-rag-agent"}