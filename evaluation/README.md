# RAG Evaluation Pack

청년 정책 RAG/LLM 서비스 평가용 파일 세트입니다.

## 파일 구성

- `evaluation_dataset.jsonl`: 평가 질의셋 10개 및 `reference_answer` 포함
- `evaluate_rag.py`: FastAPI `/chat` 또는 `/api/chat` 자동 호출, 규칙 기반 평가, BLEU/ROUGE 계산
- `llm_judge_prompt.py`: LLM-as-a-Judge 프롬프트 템플릿
- `evaluation_report_template.md`: 평가 보고서 템플릿
- `README.md`: 실행 방법 안내

## 평가 방식

### 1. 규칙 기반 평가

API 응답 JSON을 기준으로 다음 항목을 자동 점검합니다.

- 라우팅 도메인 일치 여부
- 추천 결과 개수
- 마감 공고 추천 여부
- `internal_search_sufficient` 값
- `next_action` 값
- `external_search_status`, `external_search_targets`
- `tool_trace` 존재 여부

### 2. BLEU/ROUGE 평가

`evaluation_dataset.jsonl`의 `reference_answer`와 실제 응답의 `answer`를 비교하여 다음 지표를 계산합니다.

- BLEU
- ROUGE-1 F1
- ROUGE-2 F1
- ROUGE-L F1

주의: 정책 추천형 RAG에서는 같은 정책을 맞게 추천해도 문장 표현이 다르면 BLEU/ROUGE가 낮게 나올 수 있습니다. 따라서 BLEU/ROUGE는 참고 지표로 사용하고, 마감 공고 배제, Groundedness, ReAct trace 품질을 함께 확인해야 합니다.

### 3. LLM-as-a-Judge 입력 생성

`--write-judge-inputs` 옵션을 사용하면 `judge_inputs.jsonl`이 생성됩니다.  
이 파일은 LLM Judge에 넣어 Context Relevance, Groundedness, Answer Relevance, Freshness Safety, ReAct Trace Quality, Reference Alignment를 평가하는 데 사용합니다.

## 설치 의존성

추가 의존성 없이 Python 표준 라이브러리만 사용합니다.

## 파일 배치

프로젝트 루트 기준으로 다음과 같이 배치합니다.

```text
프로젝트 루트/
└─ evaluation/
   ├─ evaluation_dataset.jsonl
   ├─ evaluate_rag.py
   ├─ llm_judge_prompt.py
   ├─ evaluation_report_template.md
   └─ README.md
```

## 실행 예시

FastAPI 서버를 먼저 실행합니다.

```bash
uvicorn backend.main:app --reload
```

그 다음 평가를 실행합니다.

```bash
python evaluation/evaluate_rag.py \
  --dataset evaluation/evaluation_dataset.jsonl \
  --base-url http://127.0.0.1:8000 \
  --endpoint /chat \
  --write-judge-inputs
```

API가 `/api/chat`이면 다음처럼 실행합니다.

```bash
python evaluation/evaluate_rag.py \
  --dataset evaluation/evaluation_dataset.jsonl \
  --base-url http://127.0.0.1:8000 \
  --endpoint /api/chat \
  --write-judge-inputs
```

## 생성 결과

기본 산출물은 `evaluation/result/`에 생성됩니다.

```text
evaluation/result/evaluation_results.json
evaluation/result/evaluation_results.md
evaluation/result/judge_inputs.jsonl
```

저장 위치를 바꾸고 싶으면 `--output-dir`를 사용합니다.

```bash
python evaluation/evaluate_rag.py --output-dir evaluation/result
```

## 결과 해석

- `evaluation_results.json`: 케이스별 원본 응답, rule check, BLEU/ROUGE 상세값 확인
- `evaluation_results.md`: 발표/보고서에 붙이기 좋은 요약 결과
- `judge_inputs.jsonl`: LLM-as-a-Judge 입력 데이터

BLEU/ROUGE 값은 참고용이며, 최종 평가는 다음 항목을 함께 봅니다.

- 추천 정책이 질문과 관련 있는가
- 마감 공고를 추천하지 않았는가
- 답변이 source_url, deadline_status 등 응답 JSON 근거에 기반하는가
- 내부 검색 결과가 부족할 때 외부 공식 출처 fallback 계획으로 분기했는가
