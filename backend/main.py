import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.api import chat, policies

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="청년 정책 RAG 에이전트",
    description="청년 정책 정보를 자연어로 검색하고 추천하는 API 서버",
    version="0.1.0",
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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.2f}s)")
    return response


@app.get("/", tags=["Root"])
def root():
    return {"message": "청년 정책 RAG 에이전트 API 서버입니다. /docs 에서 API 명세를 확인하세요."}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "youth-policy-rag-agent"}