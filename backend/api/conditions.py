import json
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openai import OpenAI

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Conditions"])

ALLOWED_INTERESTS = ["취업", "교육", "창업", "주거", "금융", "복지"]
ALLOWED_REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "경기", "기타"]
ALLOWED_JOB_STATUSES = [
    "구직자", "재직자", "중소기업 재직자", "프리랜서",
    "예비창업자", "사업자", "학생"
]
ALLOWED_HOUSING_STATUSES = ["월세", "전세", "자가", "무주택", "기타"]


class ConditionExtractRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ExtractedConditions(BaseModel):
    age: int | None = None
    region: str | None = None
    income: str | None = None
    job_status: str | None = None
    housing_status: str | None = None
    interest: list[str] = Field(default_factory=list)


def _safe_json_loads(text: str) -> dict[str, Any]:
    text = text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        text = text[start:end + 1]

    return json.loads(text)


def _normalize_result(data: dict[str, Any]) -> dict[str, Any]:
    interest = data.get("interest") or []
    if isinstance(interest, str):
        interest = [interest]

    interest = [
        item for item in interest
        if item in ALLOWED_INTERESTS
    ]

    region = data.get("region")
    if region not in ALLOWED_REGIONS:
        region = None

    job_status = data.get("job_status")
    if job_status not in ALLOWED_JOB_STATUSES:
        job_status = None

    housing_status = data.get("housing_status")
    if housing_status not in ALLOWED_HOUSING_STATUSES:
        housing_status = None

    age = data.get("age")
    try:
        age = int(age) if age is not None else None
    except (TypeError, ValueError):
        age = None

    income = data.get("income")
    if income is not None:
        income = str(income)

    return {
        "age": age,
        "region": region,
        "income": income,
        "job_status": job_status,
        "housing_status": housing_status,
        "interest": list(dict.fromkeys(interest)),
    }


def _fallback_extract(message: str) -> dict[str, Any]:
    """
    OpenAI 호출 실패 시 최소한 기존 rule-based parser를 사용.
    app_streamlit/utils/condition_parser.py를 백엔드에서 직접 import하기 애매하면
    여기서는 빈 값 반환만 해도 됨.
    """
    return {
        "age": None,
        "region": None,
        "income": None,
        "job_status": None,
        "housing_status": None,
        "interest": [],
    }


@router.post(
    "/conditions/extract",
    response_model=ExtractedConditions,
    summary="자연어 조건 추출",
    description="사용자 자연어 입력에서 나이, 지역, 고용상태, 주거상태, 관심 분야를 추출합니다.",
)
def extract_conditions(request: ConditionExtractRequest) -> ExtractedConditions:
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="입력 문장이 비어 있습니다.")

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = f"""
너는 청년정책 검색 서비스의 조건 추출기다.

사용자 문장을 보고 아래 JSON 형식만 반환해라.
설명 문장, 마크다운, 코드블록은 절대 쓰지 마라.

허용 관심 분야:
{ALLOWED_INTERESTS}

허용 지역:
{ALLOWED_REGIONS}

허용 고용상태:
{ALLOWED_JOB_STATUSES}

허용 주거상태:
{ALLOWED_HOUSING_STATUSES}

분류 기준:
- 집, 주택, 방, 원룸, 자취, 거주, 분양, 청약, 임대, 전세, 월세, 보증금, LH, 행복주택, 매입임대 → 주거
- K-Digital, KDT, 국비지원, 내일배움카드, 부트캠프, 강의, 훈련, 자격증 → 교육
- 취업, 구직, 채용, 면접, 이력서, 자소서, 인턴, 일자리 → 취업
- 창업, 스타트업, 예비창업, 사업화, 투자, IR → 창업
- 대출, 적금, 저축, 계좌, 이자, 자산, 도약계좌 → 금융
- 상담, 심리, 마음건강, 문화, 복지, 교통비, 바우처 → 복지

반환 형식:
{{
  "age": null,
  "region": null,
  "income": null,
  "job_status": null,
  "housing_status": null,
  "interest": []
}}

사용자 입력:
{message}
"""

        completion = client.chat.completions.create(
            model=os.getenv("CONDITION_EXTRACT_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": "너는 JSON만 반환하는 조건 추출기다.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
        )

        raw = completion.choices[0].message.content or "{}"
        parsed = _safe_json_loads(raw)
        normalized = _normalize_result(parsed)

        return ExtractedConditions(**normalized)

    except Exception as e:
        logger.warning("[conditions/extract] LLM 조건 추출 실패: %s", e, exc_info=True)
        fallback = _fallback_extract(message)
        return ExtractedConditions(**fallback)