import os
from dataclasses import dataclass
from typing import Any, Optional

import chromadb
from chromadb.api.models.Collection import Collection
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


@dataclass
class VectorSearchResult:
    chunk_id: str
    policy_id: str
    policy_name: str
    domain: str
    text: str
    score: float
    distance: float
    source_url: str
    metadata: dict[str, Any]


class YouthPolicyVectorStore:
    """
    청년 정책 chunk 검색용 Chroma Vector Store.

    - 저장 위치: data/vector_db/
    - 컬렉션명: youth_policy_chunks
    - 임베딩 모델 기본값: text-embedding-3-small
    """

    def __init__(
        self,
        persist_dir: str = "data/vector_db",
        collection_name="youth_opportunity_chunks",
        embedding_model: Optional[str] = None,
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model = (
            embedding_model
            or os.getenv("OPENAI_EMBEDDING_MODEL")
            or "text-embedding-3-small"
        )

        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)

        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "description": "Youth policy RAG chunks",
                "hnsw:space": "cosine",
            },
        )

    def get_collection(self) -> Collection:
        return self.collection

    def count(self) -> int:
        return self.collection.count()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )

        return [item.embedding for item in response.data]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]

    def add_chunks(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        """
        Chroma에 chunk를 upsert한다.
        같은 id가 이미 있으면 덮어쓴다.
        """
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[dict[str, Any]] = None,
    ) -> list[VectorSearchResult]:
        """
        query를 OpenAI embedding으로 변환한 뒤 Chroma에서 Top-k 검색한다.

        반환값에는 완료 기준에 맞게
        policy_id, policy_name, score, source_url이 포함된다.
        """
        query_embedding = self.embed_query(query)

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        search_results: list[VectorSearchResult] = []

        for chunk_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            metadata = metadata or {}

            # cosine distance 기준: 작을수록 유사함.
            # score는 보기 편하게 1 - distance로 둔다.
            score = 1.0 - float(distance)

            search_results.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    policy_id=str(metadata.get("policy_id", "")),
                    policy_name=str(metadata.get("policy_name", "")),
                    domain=str(metadata.get("domain", "")),
                    text=document or "",
                    score=score,
                    distance=float(distance),
                    source_url=str(metadata.get("source_url", "")),
                    metadata=metadata,
                )
            )

        return search_results

def match_age(user_age: int | None, age_min: int, age_max: int) -> bool:
    if user_age is None:
        return True

    # -1은 연령 제한 없음 / 확인 필요로 보고 통과
    if age_min == -1 or age_max == -1:
        return True

    return age_min <= user_age <= age_max


def match_region(user_region_code: Optional[str], region_code: str) -> bool:
    if user_region_code is None:
        return True

    if not region_code:
        return True

    codes = [code.strip() for code in region_code.split(",") if code.strip()]

    # 전국/전체 정책 처리
    if "ALL" in codes or "00000" in codes or "전국" in codes:
        return True

    # 정확히 일치하면 통과
    if user_region_code in codes:
        return True

    # 시/도 단위 코드 처리
    # 예: 서울 전체 11000 -> 서울 자치구 11110, 11140, ... 허용
    if len(user_region_code) == 5 and user_region_code.endswith("000"):
        sido_prefix = user_region_code[:2]
        return any(code.startswith(sido_prefix) for code in codes)

    return False


def search_with_filters(
    vector_store,
    query: str,
    user_age: int | None = None,
    user_region_code: str | None = None,
    top_k: int = 5,
    fetch_k: int = 30,
):
    raw_results = vector_store.search(query=query, top_k=fetch_k)

    filtered = []

    for result in raw_results:
        metadata = result.metadata

        age_min = int(metadata.get("age_min", -1))
        age_max = int(metadata.get("age_max", -1))
        region_code = str(metadata.get("region_code", ""))

        if not match_age(user_age, age_min, age_max):
            continue

        if not match_region(user_region_code, region_code):
            continue

        filtered.append(result)

        if len(filtered) >= top_k:
            break

    return filtered

def get_vector_store() -> YouthPolicyVectorStore:
    """
    FastAPI service layer에서 재사용할 기본 VectorStore 객체 생성 함수.
    """
    return YouthPolicyVectorStore()

def result_to_dict(result: VectorSearchResult) -> dict[str, Any]:
    """
    VectorSearchResult를 API/RAG 서비스에서 쓰기 쉬운 dict로 변환한다.
    """
    return {
        "chunk_id": result.chunk_id,
        "policy_id": result.policy_id,
        "policy_name": result.policy_name,
        "domain": result.domain,
        "score": result.score,
        "distance": result.distance,
        "text": result.text,
        "source_url": result.source_url,
        "metadata": result.metadata,
    }


def search_policy_chunks(
    query: str,
    top_k: int = 5,
    fetch_k: int = 50,
    filters: Optional[dict[str, Any]] = None,
    vector_store: Optional[YouthPolicyVectorStore] = None,
) -> list[dict[str, Any]]:
    """
    Retriever에서 호출하기 위한 Vector DB 검색 함수.

    filters 예시:
    {
        "user_age": 25,
        "user_region_code": "11000",
        "domain": "일자리"
    }
    """
    if vector_store is None:
        vector_store = get_vector_store()

    filters = filters or {}

    user_age = filters.get("user_age")
    user_region_code = filters.get("user_region_code")
    domain = filters.get("domain")
    source_category = filters.get("source_category")

    raw_results = search_with_filters(
        vector_store=vector_store,
        query=query,
        user_age=user_age,
        user_region_code=user_region_code,
        top_k=fetch_k,
        fetch_k=fetch_k,
    )

    # source_category는 데이터 유형 필터이므로 후처리에서 우선 적용한다.
    # 단, 결과가 너무 적으면 Retriever 단계 fallback을 위해 원본을 유지한다.
    if source_category:
        category_filtered = []

        for result in raw_results:
            result_source_category = str(result.metadata.get("source_category", ""))

            if result_source_category == source_category:
                category_filtered.append(result)

        if len(category_filtered) >= top_k:
            raw_results = category_filtered

    # domain 필터는 Chroma where로 강하게 걸기보다 후처리로 느슨하게 적용
    if domain:
        domain_aliases = {
            "교육": {"교육", "education", "training"},
            "창업": {"창업", "startup", "startup_notice"},
            "일자리": {"일자리", "job", "employment", "work"},
            "주거": {"주거", "housing"},
            "금융": {"금융", "finance"},
            "복지문화": {"복지문화", "welfare", "culture"},
            "참여권리": {"참여권리", "participation", "rights"},
        }
        expected_domains = domain_aliases.get(str(domain), {str(domain)})

        domain_filtered = []

        for result in raw_results:
            result_domain = str(result.metadata.get("domain", ""))

            if (
                domain in result_domain
                or result_domain in str(domain)
                or result_domain in expected_domains
            ):
                domain_filtered.append(result)

        # 도메인 필터 결과가 너무 적으면 fallback을 위해 원본 유지
        if len(domain_filtered) >= top_k:
            raw_results = domain_filtered

    return [result_to_dict(result) for result in raw_results[:top_k]]