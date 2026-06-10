# backend/db/vector_store.py

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.api.models.Collection import Collection


DEFAULT_COLLECTION_NAME = "youth_policy_chunks"
DEFAULT_DB_PATH = "data/vector_db"


def _get_openai_embedding_function():
    """
    OPENAI_API_KEY가 있으면 OpenAI Embeddings 사용.
    없으면 None 반환 → Chroma 기본 embedding function 사용.

    프로젝트 기준:
    - OPENAI_EMBEDDING_MODEL=text-embedding-3-small 권장
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    try:
        from chromadb.utils import embedding_functions

        model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=model_name,
        )

    except Exception as e:
        print(f"[WARN] OpenAI embedding function 초기화 실패: {e}")
        print("[WARN] Chroma 기본 embedding function을 사용합니다.")
        return None


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _safe_int(value: Any, default: int = -1) -> int:
    if value is None or value == "":
        return default

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, int):
        return value

    try:
        return int(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in ["true", "1", "yes", "y"]:
        return True

    if text in ["false", "0", "no", "n"]:
        return False

    return default


def _normalize_metadata_value(value: Any) -> Any:
    """
    Chroma metadata는 str, int, float, bool, None 정도만 안전하다.
    list/dict는 문자열로 변환한다.
    """
    if value is None:
        return ""

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, list):
        return ",".join([_safe_str(v) for v in value if _safe_str(v)])

    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)

    return _safe_str(value)


def normalize_chunk(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    목표 구조:
    {
      chunk_id,
      policy_id,
      policy_name,
      domain,
      text,
      metadata: {...}
    }

    단, 기존 chunks.jsonl 구조(content, top-level source_url 등)도 어느 정도 fallback 지원.
    """
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    text = (
        raw.get("text")
        or raw.get("content")
        or metadata.get("text")
        or ""
    )

    policy_id = raw.get("policy_id") or metadata.get("policy_id")
    policy_name = raw.get("policy_name") or metadata.get("policy_name")
    domain = raw.get("domain") or metadata.get("domain")

    source = metadata.get("source") or raw.get("source")
    source_url = metadata.get("source_url") or raw.get("source_url")
    age_min = metadata.get("age_min", raw.get("age_min", -1))
    age_max = metadata.get("age_max", raw.get("age_max", -1))
    region_code = (
        metadata.get("region_code")
        or metadata.get("region_codes")
        or raw.get("region_code")
        or raw.get("region_codes")
        or ""
    )
    info_score = metadata.get("info_score", raw.get("info_score", 0))
    needs_detail_check = metadata.get(
        "needs_detail_check",
        raw.get("needs_detail_check", True),
    )

    normalized_metadata = {
        "policy_id": _safe_str(policy_id),
        "policy_name": _safe_str(policy_name),
        "domain": _safe_str(domain),
        "source": _safe_str(source),
        "source_url": _safe_str(source_url),
        "age_min": _safe_int(age_min),
        "age_max": _safe_int(age_max),
        "region_code": _normalize_metadata_value(region_code),
        "info_score": _safe_int(info_score, default=0),
        "needs_detail_check": _safe_bool(needs_detail_check, default=True),
    }

    # 있으면 같이 보존해두면 나중에 유용함
    optional_fields = [
        "section",
        "application_url",
    ]

    for field in optional_fields:
        value = metadata.get(field, raw.get(field))
        if value is not None:
            normalized_metadata[field] = _normalize_metadata_value(value)

    return {
        "id": _safe_str(raw.get("chunk_id")),
        "document": _safe_str(text),
        "metadata": normalized_metadata,
    }


class YouthPolicyVectorStore:
    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        use_openai_embedding: bool = True,
    ):
        self.db_path = db_path
        self.collection_name = collection_name

        Path(db_path).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=db_path)

        embedding_function = (
            _get_openai_embedding_function()
            if use_openai_embedding
            else None
        )

        if embedding_function is not None:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )

    def reset_collection(self) -> Collection:
        """
        기존 컬렉션 삭제 후 재생성.
        재색인할 때 사용.
        """
        try:
            self.client.delete_collection(name=self.collection_name)
        except Exception:
            pass

        embedding_function = _get_openai_embedding_function()

        if embedding_function is not None:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
        else:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        return self.collection

    def count(self) -> int:
        return self.collection.count()

    def load_chunks_from_jsonl(self, jsonl_path: str) -> List[Dict[str, Any]]:
        path = Path(jsonl_path)

        if not path.exists():
            raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

        chunks = []

        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()

                if not line:
                    continue

                try:
                    raw = json.loads(line)
                    chunk = normalize_chunk(raw)

                    if not chunk["id"]:
                        print(f"[WARN] line {line_no}: chunk_id 없음 → skip")
                        continue

                    if not chunk["document"]:
                        print(f"[WARN] line {line_no}: text/document 없음 → skip")
                        continue

                    chunks.append(chunk)

                except Exception as e:
                    print(f"[WARN] line {line_no}: JSON 파싱/정규화 실패 → {e}")

        return chunks

    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """
        chunks를 Chroma에 batch 단위로 적재한다.
        이미 같은 id가 있으면 add에서 오류가 날 수 있으므로,
        재색인 시에는 reset_collection=True 사용 권장.
        """
        total = len(chunks)

        for start in range(0, total, batch_size):
            batch = chunks[start:start + batch_size]

            ids = [item["id"] for item in batch]
            documents = [item["document"] for item in batch]
            metadatas = [item["metadata"] for item in batch]

            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

            print(f"[INFO] indexed {min(start + batch_size, total)} / {total}")

        return total

    def build_from_jsonl(
        self,
        jsonl_path: str,
        batch_size: int = 100,
        reset: bool = True,
    ) -> Dict[str, Any]:
        if reset:
            self.reset_collection()

        chunks = self.load_chunks_from_jsonl(jsonl_path)
        indexed_count = self.add_chunks(chunks, batch_size=batch_size)

        return {
            "collection_name": self.collection_name,
            "db_path": self.db_path,
            "input_path": jsonl_path,
            "loaded_count": len(chunks),
            "indexed_count": indexed_count,
            "collection_count": self.count(),
        }
        
    def search(
    self,
    query: str,
    top_k: int = 5,
    where: Optional[Dict[str, Any]] = None,
    exclude_source_section: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Chroma 검색 결과를 서비스에서 쓰기 좋은 형태로 변환한다.
        기본적으로 source section은 검색 결과에서 제외한다.
        """
        if not query.strip():
            return []

        # source chunk를 후처리에서 제거할 것이므로 더 많이 가져온다.
        fetch_k = top_k * 5 if exclude_source_section else top_k

        result = self.collection.query(
            query_texts=[query],
            n_results=fetch_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        results = []

        for chunk_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            metadata = metadata or {}

            if exclude_source_section and metadata.get("section") == "source":
                continue

            score = None
            if distance is not None:
                score = 1 - float(distance)

            results.append(
                {
                    "chunk_id": chunk_id,
                    "text": document,
                    "policy_id": metadata.get("policy_id", ""),
                    "policy_name": metadata.get("policy_name", ""),
                    "domain": metadata.get("domain", ""),
                    "source_url": metadata.get("source_url", ""),
                    "score": score,
                    "distance": distance,
                    "metadata": metadata,
                }
            )

            if len(results) >= top_k:
                break

        return results

    
    # def search(
    #     self,
    #     query: str,
    #     top_k: int = 5,
    #     where: Optional[Dict[str, Any]] = None,
    # ) -> List[Dict[str, Any]]:
    #     """
    #     Chroma 검색 결과를 서비스에서 쓰기 좋은 형태로 변환한다.
    #     반환 필드:
    #     - chunk_id
    #     - text
    #     - policy_id
    #     - policy_name
    #     - domain
    #     - source_url
    #     - score
    #     - distance
    #     - metadata
    #     """
    #     if not query.strip():
    #         return []

    #     result = self.collection.query(
    #         query_texts=[query],
    #         n_results=top_k,
    #         where=where,
    #         include=["documents", "metadatas", "distances"],
    #     )

    #     ids = result.get("ids", [[]])[0]
    #     documents = result.get("documents", [[]])[0]
    #     metadatas = result.get("metadatas", [[]])[0]
    #     distances = result.get("distances", [[]])[0]

    #     results = []

    #     for chunk_id, document, metadata, distance in zip(
    #         ids,
    #         documents,
    #         metadatas,
    #         distances,
    #     ):
    #         # cosine distance 기준이면 1 - distance를 유사도 점수처럼 볼 수 있음
    #         score = None
    #         if distance is not None:
    #             score = 1 - float(distance)

    #         metadata = metadata or {}

    #         results.append(
    #             {
    #                 "chunk_id": chunk_id,
    #                 "text": document,
    #                 "policy_id": metadata.get("policy_id", ""),
    #                 "policy_name": metadata.get("policy_name", ""),
    #                 "domain": metadata.get("domain", ""),
    #                 "source_url": metadata.get("source_url", ""),
    #                 "score": score,
    #                 "distance": distance,
    #                 "metadata": metadata,
    #             }
    #         )

    #     return results