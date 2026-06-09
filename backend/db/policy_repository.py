import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# policies.json 경로 (프로젝트 루트 기준)
# 정승님과 경로 확정 후 수정
POLICIES_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "policies.json"

_cache: list[dict] | None = None


def load_policies() -> list[dict]:
    """policies.json을 읽어 캐시에 저장합니다."""
    global _cache
    if _cache is not None:
        return _cache

    if not POLICIES_PATH.exists():
        logger.error(f"[DB] policies.json 없음: {POLICIES_PATH}")
        raise FileNotFoundError(f"policies.json 파일을 찾을 수 없습니다: {POLICIES_PATH}")

    try:
        with open(POLICIES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 최상위가 리스트인 경우와 {"policies": [...]} 형태 모두 대응
        if isinstance(data, list):
            _cache = data
        elif isinstance(data, dict) and "policies" in data:
            _cache = data["policies"]
        else:
            raise ValueError("policies.json 형식이 올바르지 않습니다.")

        logger.info(f"[DB] policies.json 로드 완료: {len(_cache)}개 정책")
        return _cache

    except json.JSONDecodeError as e:
        logger.error(f"[DB] policies.json 파싱 실패: {e}")
        raise ValueError(f"policies.json 파싱 실패: {e}")


def get_all_policies() -> list[dict]:
    return load_policies()


def get_policy_by_id(policy_id: str) -> dict | None:
    policies = load_policies()
    for p in policies:
        if p.get("policy_id") == policy_id:
            return p
    return None


def search_policies_by_keyword(keyword: str) -> list[dict]:
    policies = load_policies()
    keyword_lower = keyword.lower()
    return [
        p for p in policies
        if keyword_lower in (p.get("policy_name") or "").lower()
        or keyword_lower in (p.get("summary") or "").lower()
        or keyword_lower in (p.get("support_content") or "").lower()
    ]