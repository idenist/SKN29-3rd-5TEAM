import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from tqdm import tqdm

# 프로젝트 루트에서 실행하지 않아도 backend import가 되도록 처리
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backend.db.vector_store import YouthPolicyVectorStore


load_dotenv()


METADATA_FIELDS = [
    "policy_id",
    "policy_name",
    "domain",
    "source",
    "source_url",
    "age_min",
    "age_max",
    "region_code",
    "info_score",
    "needs_detail_check",
]


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def safe_int(value: Any, default: int = -1) -> int:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, int):
        return value

    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def safe_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in {"true", "1", "yes", "y"}:
        return True

    if text in {"false", "0", "no", "n"}:
        return False

    return default


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Chroma metadata는 None, list, dict 같은 값을 싫어할 수 있다.
    문자열, int, float, bool 중심으로 정규화한다.
    """
    clean = {}

    for key in METADATA_FIELDS:
        value = metadata.get(key)

        if key in {"age_min", "age_max", "info_score"}:
            clean[key] = safe_int(value, default=-1 if key != "info_score" else 0)

        elif key == "needs_detail_check":
            clean[key] = safe_bool(value, default=True)

        else:
            clean[key] = safe_str(value)

    return clean


def normalize_chunk(raw: dict[str, Any]) -> dict[str, Any]:
    """
    입력 파일이 아래 둘 중 무엇이든 Chroma 적재용 구조로 맞춘다.

    1. 목표 구조:
       {
         "chunk_id": "...",
         "text": "...",
         "metadata": {...}
       }

    2. 기존 구조:
       {
         "chunk_id": "...",
         "content": "...",
         "policy_id": "...",
         ...
       }
    """
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    chunk_id = safe_str(raw.get("chunk_id"))
    text = safe_str(raw.get("text") or raw.get("content"))

    policy_id = safe_str(metadata.get("policy_id") or raw.get("policy_id"))
    policy_name = safe_str(metadata.get("policy_name") or raw.get("policy_name"))
    domain = safe_str(metadata.get("domain") or raw.get("domain"))

    normalized_metadata = {
        "policy_id": policy_id,
        "policy_name": policy_name,
        "domain": domain,
        "source": safe_str(metadata.get("source") or raw.get("source")),
        "source_url": safe_str(metadata.get("source_url") or raw.get("source_url")),
        "age_min": metadata.get("age_min", raw.get("age_min", -1)),
        "age_max": metadata.get("age_max", raw.get("age_max", -1)),
        "region_code": safe_str(
            metadata.get("region_code")
            or metadata.get("region_codes")
            or raw.get("region_code")
            or raw.get("region_codes")
        ),
        "info_score": metadata.get("info_score", raw.get("info_score", 0)),
        "needs_detail_check": metadata.get(
            "needs_detail_check",
            raw.get("needs_detail_check", True),
        ),
    }

    return {
        "id": chunk_id,
        "document": text,
        "metadata": sanitize_metadata(normalized_metadata),
    }


def read_chunks(input_path: Path) -> list[dict[str, Any]]:
    chunks = []
    error_count = 0

    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                raw = json.loads(line)
                chunk = normalize_chunk(raw)

                if not chunk["id"]:
                    raise ValueError("empty chunk_id")

                if not chunk["document"]:
                    raise ValueError("empty document text")

                if not chunk["metadata"]["policy_id"]:
                    raise ValueError("empty policy_id")

                chunks.append(chunk)

            except Exception as e:
                error_count += 1
                print(f"[WARN] line {line_no} skipped: {repr(e)}")

    if error_count > 0:
        print(f"[WARN] skipped rows: {error_count}")

    return chunks


def batch_list(items: list[Any], batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def build_vector_db(
    input_path: Path,
    persist_dir: str,
    collection_name: str,
    batch_size: int,
    reset: bool,
):
    vector_store = YouthPolicyVectorStore(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )

    if reset:
        try:
            vector_store.chroma_client.delete_collection(collection_name)
            print(f"[INFO] deleted existing collection: {collection_name}")
        except Exception:
            print(f"[INFO] collection did not exist or could not be deleted: {collection_name}")

        vector_store = YouthPolicyVectorStore(
            persist_dir=persist_dir,
            collection_name=collection_name,
        )

    chunks = read_chunks(input_path)

    print(f"[INFO] input_path: {input_path}")
    print(f"[INFO] persist_dir: {persist_dir}")
    print(f"[INFO] collection_name: {collection_name}")
    print(f"[INFO] chunks to insert: {len(chunks)}")

    for batch in tqdm(list(batch_list(chunks, batch_size)), desc="Embedding & upserting"):
        ids = [item["id"] for item in batch]
        documents = [item["document"] for item in batch]
        metadatas = [item["metadata"] for item in batch]

        embeddings = vector_store.embed_texts(documents)

        vector_store.add_chunks(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    total_count = vector_store.count()

    print("[INFO] Chroma 적재 완료")
    print(f"[INFO] collection count: {total_count}")

    return vector_store


def run_smoke_test(vector_store: YouthPolicyVectorStore, query: str, top_k: int):
    print("\n[INFO] Smoke Test")
    print(f"[INFO] query: {query}")

    results = vector_store.search(query=query, top_k=top_k)

    for idx, item in enumerate(results, start=1):
        print("-" * 80)
        print(f"[{idx}] policy_name: {item.policy_name}")
        print(f"    policy_id: {item.policy_id}")
        print(f"    score: {item.score:.4f}")
        print(f"    distance: {item.distance:.4f}")
        print(f"    domain: {item.domain}")
        print(f"    source_url: {item.source_url}")
        print(f"    text: {item.text[:200].replace(chr(10), ' ')}...")


def main():
    parser = argparse.ArgumentParser(
        description="Build Chroma Vector DB from youth policy chunks JSONL."
    )

    parser.add_argument(
        "--input",
        default="data/processed/chunks_for_chroma.jsonl",
        help="입력 JSONL 경로. 권장: data/processed/chunks_for_chroma.jsonl",
    )

    parser.add_argument(
        "--persist-dir",
        default="data/vector_db",
        help="Chroma Vector DB 저장 경로",
    )

    parser.add_argument(
        "--collection-name",
        default="youth_policy_chunks",
        help="Chroma collection name",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="OpenAI embedding/upsert batch size",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="기존 collection 삭제 후 재생성",
    )

    parser.add_argument(
        "--test-query",
        default="서울에 사는 25세 취업준비생이 받을 수 있는 청년 지원 정책 알려줘",
        help="적재 후 테스트 검색 쿼리",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="테스트 검색 결과 개수",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    vector_store = build_vector_db(
        input_path=input_path,
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
        batch_size=args.batch_size,
        reset=args.reset,
    )

    run_smoke_test(
        vector_store=vector_store,
        query=args.test_query,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    main()