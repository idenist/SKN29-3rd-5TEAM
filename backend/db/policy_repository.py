import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# opportunities.json 경로 (프로젝트 루트 기준)
OPPORTUNITIES_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "opportunities.json"

_cache: list[dict] | None = None
_cache_map: dict[str, dict] | None = None  # item_id → dict, O(1) 조회용


def load_policies() -> list[dict]:
    """opportunities.json을 읽어 캐시에 저장합니다."""
    global _cache, _cache_map
    if _cache is not None:
        return _cache

    if not OPPORTUNITIES_PATH.exists():
        logger.error(f"[DB] opportunities.json 없음: {OPPORTUNITIES_PATH}")
        raise FileNotFoundError(f"opportunities.json 파일을 찾을 수 없습니다: {OPPORTUNITIES_PATH}")

    try:
        with open(OPPORTUNITIES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 최상위가 리스트인 경우와 {"items": [...]} 형태 모두 대응
        if isinstance(data, list):
            _cache = data
        elif isinstance(data, dict):
            _cache = next(iter(data.values()))  # 첫 번째 값이 리스트라고 가정
        else:
            raise ValueError("opportunities.json 형식이 올바르지 않습니다.")

        # O(1) 조회용 dict 생성
        _cache_map = {d["item_id"]: d for d in _cache if "item_id" in d}

        logger.info(f"[DB] opportunities.json 로드 완료: {len(_cache)}개 항목")
        return _cache

    except json.JSONDecodeError as e:
        logger.error(f"[DB] opportunities.json 파싱 실패: {e}")
        raise ValueError(f"opportunities.json 파싱 실패: {e}")


def get_all_policies(source_category: str | None = None) -> list[dict]:
    """전체 목록 반환. source_category로 필터 가능 (policy/startup_notice/training)"""
    policies = load_policies()
    if source_category:
        return [p for p in policies if p.get("source_category") == source_category]
    return policies


def get_policy_by_id(item_id: str) -> dict | None:
    """item_id 기준 O(1) 조회"""
    load_policies()  # 캐시 초기화 보장
    return _cache_map.get(item_id) if _cache_map else None


def search_policies_by_keyword(keyword: str, source_category: str | None = None) -> list[dict]:
    """키워드 검색. source_category 필터 선택 가능"""
    policies = get_all_policies(source_category)
    keyword_lower = keyword.lower()
    return [
        p for p in policies
        if keyword_lower in (p.get("title") or p.get("policy_name") or "").lower()
        or keyword_lower in (p.get("summary") or p.get("policy_summary") or "").lower()
        or keyword_lower in (p.get("support_content") or "").lower()
    ]