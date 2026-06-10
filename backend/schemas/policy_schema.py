from pydantic import BaseModel, Field
from typing import Optional


class PolicySummary(BaseModel):
    policy_id: str = Field(..., description="정책 ID")
    policy_name: str = Field(..., description="정책명")
    domain: str = Field(..., description="도메인 (일자리/주거/교육/복지/참여)")
    sub_domain: Optional[str] = Field(None, description="세부 도메인")
    summary: Optional[str] = Field(None, description="정책 요약")
    organization: Optional[str] = Field(None, description="담당 기관")
    application_period: str = Field("정보 없음", description="신청 기간")
    needs_detail_check: bool = Field(False, description="상세 확인 필요 여부")


class PolicyDetail(BaseModel):
    policy_id: str
    policy_name: str
    domain: str
    sub_domain: Optional[str] = None
    summary: Optional[str] = None
    support_content: str = Field("정보 없음", description="지원 내용")
    application_period: str = Field("정보 없음", description="신청 기간")
    application_method: str = Field("정보 없음", description="신청 방법")
    required_documents: str = Field("정보 없음", description="제출 서류")
    application_url: Optional[str] = Field(None, description="신청 URL")
    reference_url_1: Optional[str] = Field(None, description="참고 URL")
    age_min: Optional[int] = Field(None, description="최소 나이")
    age_max: Optional[int] = Field(None, description="최대 나이")
    needs_detail_check: bool = Field(False, description="상세 확인 필요 여부")
    raw_text: Optional[str] = Field(None, description="원본 텍스트")


class PoliciesResponse(BaseModel):
    total: int = Field(..., description="전체 정책 수")
    items: list[PolicySummary] = Field(..., description="정책 목록")