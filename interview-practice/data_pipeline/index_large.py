"""
index_large.py — 실제 정책 데이터 배치 적재

[관련 포트폴리오] p.12

정규화된 정책 데이터를 청크로 변환하고,
일정한 크기로 나누어 임베딩 및 Chroma 적재를 수행한다.
indexing의 공통 적재 함수를 사용한다. 이미 저장된 ID는 건너뛰므로 같은 ID의 수정 본문은 갱신하지 않는다.
"""

import json

from config import PRACTICE_DIR
from indexing import build_chunks, get_collection, index_chunks


DATA_LIMIT = None  # None이면 전체 정책 사용
BATCH_SIZE = 100


def main():
    """정규화 JSON을 읽고 새 청크만 배치로 확장 컬렉션에 적재한다."""
    # 1. 정규화된 정책 데이터 불러오기
    path = PRACTICE_DIR / "data/youth_policies_normalized.json"

    with path.open(encoding="utf-8") as f:
        policies = json.load(f)

    policies = policies[:DATA_LIMIT]

    # 2. 기존 함수를 이용해 청크 생성
    chunks = build_chunks(policies)

    print("정책 수:", len(policies))
    print("청크 수:", len(chunks))

    # 3. 확장 실험용 컬렉션 생성
    collection = get_collection("extended", for_indexing=True)

    # 4. 이미 적재된 청크는 제외한다.
    # 중간에 실행이 실패하더라도 완료된 청크를
    # 다시 임베딩하지 않도록 하기 위함이다.
    existing_ids = set(
        collection.get(include=[])["ids"]
    )

    pending = [
        chunk for chunk in chunks
        if chunk["chunk_id"] not in existing_ids
    ]

    print("기존 청크 수:", len(existing_ids))
    print("신규 적재 대상:", len(pending))

    # 5. 배치 단위 임베딩 및 적재
    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]

        index_chunks(collection, batch)

        print(
            f"적재 진행: "
            f"{start + len(batch)}/{len(pending)}"
        )

    print("최종 저장 청크 수:", collection.count())


if __name__ == "__main__":
    main()
