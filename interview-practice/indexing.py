"""정책을 청크로 나누고 벡터를 저장하는 적재 단계 (p.9~10, p.12).

main에서 policies의 레코드를 받고 Chroma 컬렉션에 본문·벡터·메타데이터를 저장한다.
retriever는 embed_texts를 질문에도 사용한다. 적재와 조회를 분리해 기존 문서 벡터를 재사용한다."""

import chromadb

from config import COLLECTION_NAME, DB_PATH, EMBEDDING_MODEL, get_openai_client


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


def get_collection():
    """설정의 저장 경로와 이름으로 Chroma 컬렉션을 열어 반환한다.

    최초 생성 시 코사인 거리를 지정한다. 기존 컬렉션을 열면 그 안의 데이터와 설정을 재사용한다.
    이 함수는 자료를 적재하지 않는다.
    """

    chroma_client = chromadb.PersistentClient(
        path=DB_PATH
    )

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={
            "hnsw": {"space": "cosine"}
        }
    )

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
