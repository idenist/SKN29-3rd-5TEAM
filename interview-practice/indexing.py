"""정책을 청크로 나누고 벡터를 저장하는 적재 단계 (p.9~10, p.12).

main에서 policies의 레코드를 받고 Chroma 컬렉션에 본문·벡터·메타데이터를 저장한다.
retriever는 embed_texts를 질문에도 사용한다. 적재와 조회를 분리해 기존 문서 벡터를 재사용한다.
내용 유형마다 한 청크를 만들므로 같은 유형의 긴 문서는 한 청크에 남는다.
"""

import chromadb
from chromadb.errors import NotFoundError

from config import COLLECTIONS, DB_PATH, EMBEDDING_MODEL, get_openai_client


def build_chunks(policies):
    """정책 목록을 chunk_id, document, metadata가 있는 딕셔너리 목록으로 펼친다.

    정책의 documents 항목마다 청크 하나를 만들고 공통 메타데이터를 복사한다.
    chunk_id는 조각을 갱신할 때, item_id는 여러 조각을 한 정책으로 묶을 때 사용한다.
    본문은 의미를 비교하고 메타데이터는 값을 정확히 대조한다. 입력은 실습 정책 형식을 전제한다.
    """

    chunks = []

    for policy in policies:
        item_id = policy["item_id"]

        # documents 딕셔너리를 순회하며 청크를 생성한다.
        # 예: chunk_type = "summary", document = "지원 내용..."
        for chunk_type, document in policy["documents"].items():

            chunk = {
                "chunk_id": f"{item_id}::{chunk_type}",
                "document": document,

                # 원본 정책의 메타데이터를 각 청크에 전달한다.
                # item_id는 검색 결과를 정책 단위로 묶을 때 사용한다.
                "metadata": {
                    **policy["metadata"],
                    "item_id": item_id,
                    "title": policy["title"],
                    "chunk_type": chunk_type
                }
            }

            chunks.append(chunk)

    return chunks


def embed_texts(texts):
    """문자열 목록을 OpenAI에 보내 입력 순서대로 벡터 목록을 반환한다.

    응답 index로 순서를 맞춰 본문과 벡터가 어긋나지 않게 한다. 검색할 질문에도
    문서와 같은 모델을 써야 같은 벡터 공간에서 비교할 수 있다. 모델을 바꾸면 재적재해야 한다.
    """

    response = get_openai_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )

    # API 응답의 index를 기준으로 입력 텍스트의 순서를 맞춘다.
    items = sorted(response.data, key=lambda item: item.index)

    return [item.embedding for item in items]


def get_collection(dataset="sample", *, for_indexing=False):
    """지정한 데이터셋의 컬렉션을 연다. 확장 DB 생성은 명시적인 배치 적재 경로에서만 허용한다."""
    if dataset not in COLLECTIONS:
        raise ValueError("DATASET은 sample 또는 extended여야 합니다.")
    name = COLLECTIONS[dataset]
    client = chromadb.PersistentClient(path=DB_PATH)
    if dataset == "sample" or for_indexing:
        return client.get_or_create_collection(name, configuration={"hnsw": {"space": "cosine"}})
    hint = f"{name} 컬렉션과 DB_PATH를 확인하세요. 확장 적재 단계는 data_pipeline.index_large입니다."
    try:
        collection = client.get_collection(name)
    except NotFoundError:
        raise ValueError(f"확장 컬렉션을 찾지 못했습니다. {hint}") from None
    if not collection.count():
        raise ValueError(f"확장 컬렉션이 비어 있습니다. {hint}")
    return collection


def index_chunks(collection, chunks):
    """컬렉션과 청크 목록을 받아 본문들을 한 번에 임베딩한 뒤 ID별로 upsert한다.

    반환값은 없고 컬렉션에 ID·본문·벡터·메타데이터가 저장된다. 같은 ID는 갱신하지만
    입력에서 사라진 청크는 자동 삭제하지 않는다. 한 배치에 담을 수 있는 실습 규모를 전제한다.
    """

    # 임베딩할 대상은 청크의 본문이다.
    texts = [chunk["document"] for chunk in chunks]

    # 여러 청크를 한 번의 API 호출로 임베딩한다.
    embeddings = embed_texts(texts)

    # upsert는 ID가 없으면 추가하고, 있으면 갱신한다.
    collection.upsert(
        ids=[chunk["chunk_id"] for chunk in chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[chunk["metadata"] for chunk in chunks]
    )
