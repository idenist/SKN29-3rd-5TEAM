from pydantic import BaseModel, Field
from typing import Optional

class PolicySummary(BaseModel):
    policy_id: str = Field(..., description="정책 ID")
    policy_name: str = Field(..., description="정책명")
    domain: str = Field(..., description="도메인 (일자리/주거/교육/복지/참여)")
    sub_domain: Optional[str] = Field(None, description="세부 도메인")
    summary: Optional[str] = Field(None, description="정책 요약")
    organization: Optional[str] = Field(None, description="담당 기관")
    source_category: Optional[str] = Field(None, description="출처 카테고리 (policy/startup_notice/training)")
    
    # application_period → 3개 필드로 분리
    application_period_text: Optional[str] = Field(None, description="신청 기간 텍스트")
    application_start_date: Optional[str] = Field(None, description="신청 시작일")
    application_end_date: Optional[str] = Field(None, description="신청 종료일")
    
    needs_detail_check: bool = Field(False, description="상세 확인 필요 여부")


class PolicyDetail(BaseModel):
    policy_id: str
    policy_name: str
    domain: str
    sub_domain: Optional[str] = None
    summary: Optional[str] = None
    organization: Optional[str] = Field(None, description="담당 기관") 
    source_category: Optional[str] = Field(None, description="출처 카테고리")
    
    # 지원 내용
    support_content: str = Field("정보 없음", description="지원 내용")
    
    # 신청 기간 — 3개 필드로 분리
    application_period_text: Optional[str] = Field(None, description="신청 기간 텍스트")
    application_start_date: Optional[str] = Field(None, description="신청 시작일")
    application_end_date: Optional[str] = Field(None, description="신청 종료일")
    
    application_method: str = Field("정보 없음", description="신청 방법")
    required_documents: str = Field("정보 없음", description="제출 서류")
    application_url: Optional[str] = Field(None, description="신청 URL")
    
    # reference_url_1 → source_url / source_url_2로 변경
    source_url: Optional[str] = Field(None, description="원문 출처 URL")
    source_url_2: Optional[str] = Field(None, description="보조 출처 URL")
    
    # 자격 조건 필드 추가
    age_min: Optional[int] = Field(None, description="최소 나이")
    age_max: Optional[int] = Field(None, description="최대 나이")
    region_codes: Optional[str] = Field(None, description="대상 지역 코드")
    participation_target: Optional[str] = Field(None, description="참여 대상 (고용 상태 등)")
    income_condition: Optional[str] = Field(None, description="소득 조건")
    
    # 품질 관련
    info_score: Optional[int] = Field(None, description="정보 충실도 점수")
    needs_detail_check: bool = Field(False, description="상세 확인 필요 여부")
    raw_text: Optional[str] = Field(None, description="원본 텍스트")


class PoliciesResponse(BaseModel):
    total: int = Field(..., description="전체 정책 수")
    items: list[PolicySummary] = Field(..., description="정책 목록")