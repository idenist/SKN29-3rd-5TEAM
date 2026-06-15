import json
import time
import random
from pathlib import Path
from openai import OpenAI
import requests
from dotenv import load_dotenv
load_dotenv()

EVAL_PATH = Path("tests/evaluation_dataset.jsonl")
OUTPUT_PATH = Path("evaluation/result/llm_judge_results.json")
FASTAPI_URL = "http://127.0.0.1:8000/api/chat"
SAMPLE_N = 10

client = OpenAI()

JUDGE_PROMPT = """당신은 RAG 시스템의 답변 품질을 평가하는 전문가입니다.
아래 질문, 검색된 컨텍스트, 생성된 답변을 보고 3가지 지표를 1~5점으로 평가하세요.

질문: {question}

검색된 정책 목록:
{context}

생성된 답변:
{answer}

다음 3가지를 JSON으로만 반환하세요 (다른 텍스트 없이):
{{
  "context_relevance": <1-5>,
  "groundedness": <1-5>,
  "answer_relevance": <1-5>,
  "context_relevance_reason": "<한 줄 이유>",
  "groundedness_reason": "<한 줄 이유>",
  "answer_relevance_reason": "<한 줄 이유>"
}}

평가 기준:
- context_relevance: 검색된 정책이 질문과 얼마나 관련 있는가 (1=전혀 무관, 5=매우 관련)
- groundedness: 답변이 검색된 정책 데이터에 근거하는가 (1=근거 없음/환각, 5=완전히 근거함)
- answer_relevance: 답변이 질문에 적절히 답하는가 (1=전혀 답 안 함, 5=완벽히 답함)"""


def call_rag(question: str) -> dict:
    payload = {"message": question, "top_k": 3}
    resp = requests.post(FASTAPI_URL, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def build_context(recommendations: list) -> str:
    lines = []
    for i, r in enumerate(recommendations, 1):
        lines.append(f"{i}. {r.get('policy_name', '')} ({r.get('source_category', '')})")
        lines.append(f"   지원내용: {r.get('support_content', '')[:100]}")
    return "\n".join(lines)


def judge(question: str, context: str, answer: str) -> dict:
    prompt = JUDGE_PROMPT.format(
        question=question,
        context=context,
        answer=answer[:1000]
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def main():
    with open(EVAL_PATH, "r", encoding="utf-8-sig") as f:
        all_rows = [
            json.loads(line)
            for line in f
            if line.strip()
        ]
    random.seed(42)
    samples = random.sample(all_rows, SAMPLE_N)

    results = []
    for i, row in enumerate(samples, 1):
        question = row["question"]
        print(f"[{i}/{SAMPLE_N}] {question[:40]}...")

        try:
            rag_result = call_rag(question)
            answer = rag_result.get("answer", "")
            recommendations = rag_result.get("recommendations", [])
            route = rag_result.get("route", "")
            context = build_context(recommendations)

            scores = judge(question, context, answer)

            results.append({
                "question": question,
                "answer_item_ids": row["answer_item_ids"],
                "route": route,
                "retrieved_policies": [r.get("policy_name") for r in recommendations],
                "answer_preview": answer[:200],
                **scores
            })

            print(f"  context_relevance={scores['context_relevance']} "
                  f"groundedness={scores['groundedness']} "
                  f"answer_relevance={scores['answer_relevance']}")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"question": question, "error": str(e)})

        time.sleep(1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    valid = [r for r in results if "error" not in r]
    if valid:
        avg_cr = sum(r["context_relevance"] for r in valid) / len(valid)
        avg_gr = sum(r["groundedness"] for r in valid) / len(valid)
        avg_ar = sum(r["answer_relevance"] for r in valid) / len(valid)
        print(f"\n=== 평가 결과 ({len(valid)}/{SAMPLE_N}건) ===")
        print(f"Context Relevance:  {avg_cr:.2f} / 5.0")
        print(f"Groundedness:       {avg_gr:.2f} / 5.0")
        print(f"Answer Relevance:   {avg_ar:.2f} / 5.0")
        print(f"결과 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()