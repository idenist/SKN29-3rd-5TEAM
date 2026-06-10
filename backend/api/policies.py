import logging
from fastapi import APIRouter, HTTPException, Query
from backend.schemas.policy_schema import PoliciesResponse, PolicySummary, PolicyDetail
from backend.db.policy_repository import get_all_policies, get_policy_by_id, search_policies_by_keyword

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Policies"])


@router.get(
    "/policies",
    response_model=PoliciesResponse,
    summary="정책 목록 조회",
    description="전체 정책 목록을 도메인/키워드 필터와 페이징으로 조회합니다.",
)
def list_policies(
    domain: str | None = Query(None, description="도메인 필터 (일자리/주거/교육/복지/참여)"),
    keyword: str | None = Query(None, description="키워드 검색"),
    limit: int = Query(20, ge=1, le=100, description="페이지 크기"),
    offset: int = Query(0, ge=0, description="오프셋"),
):
    try:
        if keyword:
            policies = search_policies_by_keyword(keyword)
        else:
            policies = get_all_policies()

        if domain:
            policies = [p for p in policies if p.get("domain") == domain]

        total = len(policies)
        page = policies[offset: offset + limit]

        items = [
            PolicySummary(
                policy_id=p.get("policy_id", ""),
                policy_name=p.get("policy_name", ""),
                domain=p.get("domain", ""),
                sub_domain=p.get("sub_domain"),
                summary=p.get("summary"),
                organization=p.get("organization"),
                application_period=p.get("application_period") or "정보 없음",
                needs_detail_check=p.get("needs_detail_check", False),
            )
            for p in page
        ]

        return PoliciesResponse(total=total, items=items)

    except FileNotFoundError:
        logger.error("[ERROR] policies.json 파일을 찾을 수 없습니다.")
        raise HTTPException(
            status_code=503,
            detail="정책 데이터베이스가 준비되지 않았습니다. 관리자에게 데이터 색인 상태를 확인해 주세요.",
        )
    except Exception as e:
        logger.error(f"[ERROR] /api/policies 오류: {e}")
        raise HTTPException(status_code=500, detail="정책 목록 조회 중 오류가 발생했습니다.")


@router.get(
    "/policies/{policy_id}",
    response_model=PolicyDetail,
    summary="정책 상세 조회",
    description="policy_id로 특정 정책의 상세 정보를 조회합니다.",
)
def get_policy(policy_id: str):
    try:
        policy = get_policy_by_id(policy_id)

        if policy is None:
            raise HTTPException(status_code=404, detail=f"정책 ID '{policy_id}'를 찾을 수 없습니다.")

        return PolicyDetail(
            policy_id=policy.get("policy_id", ""),
            policy_name=policy.get("policy_name", ""),
            domain=policy.get("domain", ""),
            sub_domain=policy.get("sub_domain"),
            summary=policy.get("summary"),
            support_content=policy.get("support_content") or "정보 없음",
            application_period=policy.get("application_period") or "정보 없음",
            application_method=policy.get("application_method") or "정보 없음",
            required_documents=policy.get("required_documents") or "정보 없음",
            application_url=policy.get("application_url"),
            reference_url_1=policy.get("reference_url_1"),
            age_min=policy.get("age_min"),
            age_max=policy.get("age_max"),
            needs_detail_check=policy.get("needs_detail_check", False),
            raw_text=policy.get("raw_text"),
        )

    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="정책 데이터베이스가 준비되지 않았습니다.",
        )
    except Exception as e:
        logger.error(f"[ERROR] /api/policies/{policy_id} 오류: {e}")
        raise HTTPException(status_code=500, detail="정책 상세 조회 중 오류가 발생했습니다.")