import argparse
import json
import re
from pathlib import Path
from typing import Any

from tqdm import tqdm
import sys

# 프로젝트 루트에서 실행하지 않아도 backend import가 되도록 처리
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))


from backend.db.vector_store import YouthPolicyVectorStore


def safe_int(value: Any, default: int = -1) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return default
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


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """
    Chroma metadata는 str, int, float, bool 타입만 안전하게 저장한다.
    None은 빈 문자열로 바꾸고, list/dict는 JSON 문자열로 바꾼다.
    """
    sanitized: dict[str, str | int | float | bool] = {}

    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, int):
            sanitized[key] = value
        elif isinstance(value, float):
            sanitized[key] = value
        elif isinstance(value, (list, dict)):
            sanitized[key] = json.dumps(value, ensure_ascii=False)
        else:
            sanitized[key] = str(value)

    return sanitized


def parse_age_from_content(content: str) -> tuple[int, int]:
    """
    opportunity_chunks.jsonl의 eligibility chunk에 있는 age_text만 사용한다.
    application_period_text 같은 날짜가 연령으로 오인되지 않도록 전체 숫자 스캔은 하지 않는다.
    """
    if not content:
        return -1, -1

    match = re.search(r"age_text\s*:\s*([^\n]+)", content)
    if not match:
        return -1, -1

    age_text = match.group(1)
    numbers = [int(x) for x in re.findall(r"\d{1,2}", age_text)]

    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    if len(numbers) == 1:
        return numbers[0], numbers[0]
    return -1, -1


def parse_region_codes_from_content(content: str) -> str:
    """
    opportunity_chunks.jsonl의 eligibility chunk에 있는 region_codes를 추출한다.
    """
    if not content:
        return ""

    match = re.search(r"region_codes\s*:\s*([^\n]+)", content)
    if not match:
        return ""

    return match.group(1).strip()


def build_item_profiles(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    같은 item_id에 속한 summary / eligibility / application chunk 정보를 하나의 profile로 모은다.
    age_min, age_max, region_code는 eligibility chunk에서 주로 나오므로 item 단위로 전파한다.
    """
    profiles: dict[str, dict[str, Any]] = {}

    for record in records:
        metadata = record.get("metadata") or {}
        item_id = str(
            record.get("item_id")
            or record.get("policy_id")
            or metadata.get("item_id")
            or metadata.get("policy_id")
            or ""
        ).strip()

        if not item_id:
            continue

        content = str(record.get("content") or record.get("text") or "")

        profile = profiles.setdefault(
            item_id,
            {
                "age_min": -1,
                "age_max": -1,
                "region_code": "",
                "source_url": "",
                "application_url": "",
                "source_category": "",
                "source_name": "",
                "domain": "",
                "title": "",
                "info_score": 0,
                "needs_detail_check": True,
            },
        )

        age_min, age_max = parse_age_from_content(content)
        region_code = parse_region_codes_from_content(content)

        if age_min != -1 and age_max != -1:
            profile["age_min"] = age_min
            profile["age_max"] = age_max

        if region_code:
            profile["region_code"] = region_code

        field_map = {
            "title": record.get("title") or metadata.get("title") or record.get("policy_name") or metadata.get("policy_name"),
            "domain": record.get("domain") or metadata.get("domain"),
            "source_category": record.get("source_category") or metadata.get("source_category"),
            "source_name": record.get("source_name") or metadata.get("source_name"),
            "source_url": record.get("source_url") or metadata.get("source_url"),
            "application_url": record.get("application_url") or metadata.get("application_url"),
            "info_score": record.get("info_score", metadata.get("info_score")),
            "needs_detail_check": record.get("needs_detail_check", metadata.get("needs_detail_check")),
        }

        for key, value in field_map.items():
            if value in [None, ""]:
                continue
            if key == "info_score":
                profile[key] = safe_int(value, default=0)
            elif key == "needs_detail_check":
                profile[key] = safe_bool(value, default=True)
            else:
                profile[key] = value

    return profiles


def normalize_record(
    record: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    fallback_index: int,
) -> dict[str, Any]:
    raw_metadata = record.get("metadata") or {}

    item_id = str(
        record.get("item_id")
        or record.get("policy_id")
        or raw_metadata.get("item_id")
        or raw_metadata.get("policy_id")
        or ""
    ).strip()

    if not item_id:
        raise ValueError("empty item_id")

    chunk_id = str(
        record.get("chunk_id")
        or record.get("id")
        or raw_metadata.get("chunk_id")
        or ""
    ).strip()

    if not chunk_id:
        chunk_id = f"{item_id}::{fallback_index}"

    content = str(record.get("content") or record.get("text") or "").strip()

    if not content:
        raise ValueError("empty content/text")

    profile = profiles.get(item_id, {})

    title = (
        record.get("title")
        or raw_metadata.get("title")
        or record.get("policy_name")
        or raw_metadata.get("policy_name")
        or profile.get("title")
        or ""
    )

    domain = (
        record.get("domain")
        or raw_metadata.get("domain")
        or profile.get("domain")
        or ""
    )

    source_category = (
        record.get("source_category")
        or raw_metadata.get("source_category")
        or profile.get("source_category")
        or ""
    )

    source_name = (
        record.get("source_name")
        or raw_metadata.get("source_name")
        or profile.get("source_name")
        or ""
    )

    source_url = (
        record.get("source_url")
        or raw_metadata.get("source_url")
        or profile.get("source_url")
        or ""
    )

    application_url = (
        record.get("application_url")
        or raw_metadata.get("application_url")
        or profile.get("application_url")
        or ""
    )

    age_min = safe_int(
        record.get("age_min", raw_metadata.get("age_min", profile.get("age_min", -1))),
        default=safe_int(profile.get("age_min"), default=-1),
    )
    age_max = safe_int(
        record.get("age_max", raw_metadata.get("age_max", profile.get("age_max", -1))),
        default=safe_int(profile.get("age_max"), default=-1),
    )

    if age_min == -1 or age_max == -1:
        profile_age_min = safe_int(profile.get("age_min"), default=-1)
        profile_age_max = safe_int(profile.get("age_max"), default=-1)
        if profile_age_min != -1 and profile_age_max != -1:
            age_min = profile_age_min
            age_max = profile_age_max

    region_code = (
        record.get("region_code")
        or raw_metadata.get("region_code")
        or record.get("region")
        or raw_metadata.get("region")
        or profile.get("region_code")
        or ""
    )

    direct_region_code = parse_region_codes_from_content(content)
    if direct_region_code:
        region_code = direct_region_code

    metadata = {
        **raw_metadata,
        # 신규 통합 데이터 기준
        "chunk_id": chunk_id,
        "item_id": item_id,
        "title": str(title),
        "source_category": str(source_category),
        "source_name": str(source_name),
        # 기존 RAG 코드 호환 alias
        "policy_id": item_id,
        "policy_name": str(title),
        "domain": str(domain),
        "source_url": str(source_url),
        "application_url": str(application_url),
        "age_min": age_min,
        "age_max": age_max,
        "region_code": str(region_code),
        "info_score": safe_int(
            record.get("info_score", raw_metadata.get("info_score", profile.get("info_score", 0))),
            default=0,
        ),
        "needs_detail_check": safe_bool(
            record.get(
                "needs_detail_check",
                raw_metadata.get("needs_detail_check", profile.get("needs_detail_check", True)),
            ),
            default=True,
        ),
    }

    return {
        "id": chunk_id,
        "document": content,
        "metadata": sanitize_metadata(metadata),
    }


def load_jsonl(input_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception as e:
                print(f"[WARN] line {line_no} JSON parse skipped: {repr(e)}")

    return records


def read_chunks(input_path: Path) -> list[dict[str, Any]]:
    records = load_jsonl(input_path)
    profiles = build_item_profiles(records)

    chunks: list[dict[str, Any]] = []
    error_count = 0

    for idx, raw in enumerate(records):
        try:
            chunk = normalize_record(
                record=raw,
                profiles=profiles,
                fallback_index=idx,
            )

            if not chunk["id"]:
                raise ValueError("empty chunk_id")
            if not chunk["document"]:
                raise ValueError("empty document text")
            if not chunk["metadata"]["item_id"]:
                raise ValueError("empty item_id")

            chunks.append(chunk)

        except Exception as e:
            error_count += 1
            print(f"[WARN] row {idx + 1} skipped: {repr(e)}")

    if error_count > 0:
        print(f"[WARN] skipped rows: {error_count}")

    print(f"[INFO] loaded raw records: {len(records)}")
    print(f"[INFO] built item profiles: {len(profiles)}")
    print(f"[INFO] normalized chunks: {len(chunks)}")

    return chunks


def batch_list(items: list[Any], batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start:start + batch_size]


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

    if not chunks:
        raise ValueError("No valid chunks to insert.")

    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for batch in tqdm(batch_list(chunks, batch_size), total=total_batches, desc="Embedding & upserting"):
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
        metadata = item.metadata or {}

        print("-" * 80)
        print(f"[{idx}] title: {metadata.get('title') or item.policy_name}")
        print(f"    item_id: {metadata.get('item_id') or item.policy_id}")
        print(f"    source_category: {metadata.get('source_category')}")
        print(f"    score: {item.score:.4f}")
        print(f"    distance: {item.distance:.4f}")
        print(f"    domain: {item.domain}")
        print(f"    source_url: {item.source_url}")
        print(f"    age: {metadata.get('age_min')}~{metadata.get('age_max')}")
        print(f"    region_code: {str(metadata.get('region_code', ''))[:120]}...")
        print(f"    text: {item.text[:200].replace(chr(10), ' ')}...")


def main():
    parser = argparse.ArgumentParser(
        description="Build Chroma Vector DB from integrated youth opportunity chunks JSONL."
    )

    parser.add_argument(
        "--input",
        default="data/processed/opportunity_chunks.jsonl",
        help="입력 JSONL 경로. 권장: data/processed/opportunity_chunks.jsonl",
    )

    parser.add_argument(
        "--persist-dir",
        default="data/vector_db",
        help="Chroma Vector DB 저장 경로",
    )

    parser.add_argument(
        "--collection-name",
        default="youth_opportunity_chunks",
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
        default="AI 데이터 국비지원 교육 과정 알려줘",
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
