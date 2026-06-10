# tests/test_retriever_manual.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.rag_service import retrieve_policies


def main():
    query = "서울에 사는 25살 청년이 받을 수 있는 월세 지원 정책 알려줘"

    filters = {
        "domain": "housing",
        "age": 25,
        "region_code": "11110",
        "min_score": 0.1,
    }

    results = retrieve_policies(
        query=query,
        filters=filters,
        top_k=5,
    )

    print(f"검색 결과 수: {len(results)}")

    for idx, item in enumerate(results, start=1):
        print("=" * 80)
        print(f"[{idx}] {item['policy_name']}")
        print(f"policy_id: {item['policy_id']}")
        print(f"domain: {item['domain']}")
        print(f"score: {item['score']}")
        print(f"source_url: {item['metadata']['source_url']}")
        print(f"age: {item['metadata']['age_min']} ~ {item['metadata']['age_max']}")
        print(f"needs_detail_check: {item['metadata']['needs_detail_check']}")
        print(item["text"][:300])


if __name__ == "__main__":
    main()