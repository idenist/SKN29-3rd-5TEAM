from pydantic import BaseModel, Field
from typing import Optional


class UserProfile(BaseModel):
    age: Optional[int] = Field(None, description="나이", example=25)
    region: Optional[str] = Field(None, description="거주 지역", example="서울")
    income: Optional[str] = Field(None, description="소득 수준", example="중위소득 60% 이하")
    employment_status: Optional[str] = Field(None, description="취업 상태", example="취업준비생")
    interest_domain: Optional[str] = Field(None, description="관심 도메인", example="일자리")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="사용자 질문", example="서울에 사는 25세 취준생인데 받을 수 있는 취업 지원 정책 알려줘.")
    user_profile: Optional[UserProfile] = Field(None, description="사용자 프로필 (선택)")
    top_k: int = Field(5, ge=1, le=20, description="추천 정책 개수 (1~20)")


class PolicyRecommendation(BaseModel):
    policy_id: str = Field(..., description="정책 ID")
    policy_name: str = Field(..., description="정책명")
    eligibility: str = Field("추가 확인 필요", description="자격 요건 충족 여부")
    score: float = Field(..., description="유사도 점수 (0~1)")
    reason: str = Field(..., description="추천 이유")
    support_content: str = Field("정보 없음", description="지원 내용")
    application_period: str = Field("정보 없음", description="신청 기간")
    required_documents: str = Field("정보 없음", description="제출 서류")
    source_url: Optional[str] = Field(None, description="원문 URL")
    needs_detail_check: bool = Field(False, description="상세 확인 필요 여부")
    cautions: list[str] = Field(default_factory=list, description="주의사항")


class UserConditions(BaseModel):
    age: Optional[int] = None
    region: Optional[str] = None
    income: Optional[str] = None
    employment_status: Optional[str] = None
    interest_domain: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str = Field(..., description="LLM 생성 답변")
    user_conditions: UserConditions = Field(..., description="추출된 사용자 조건")
    route: str = Field(..., description="라우팅된 정책 도메인")
    recommendations: list[PolicyRecommendation] = Field(..., description="추천 정책 목록")
    warnings: list[str] = Field(default_factory=list, description="경고 메시지")


class ErrorResponse(BaseModel):
    error: bool = True
    message: str = Field(..., description="사용자용 오류 메시지")
    detail: Optional[str] = Field(None, description="개발자용 상세 정보")
    recoverable: bool = Field(True, description="복구 가능 여부")