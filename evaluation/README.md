# RAG Evaluation Pack

청년 정책 RAG/LLM 서비스 평가용 파일 세트입니다.

## 파일 구성

- `evaluation_dataset.jsonl`: 평가 질의셋 10개
- `evaluate_rag.py`: FastAPI `/chat` 또는 `/api/chat` 자동 호출 및 규칙 기반 평가
- `llm_judge_prompt.py`: LLM-as-a-Judge 프롬프트 템플릿
- `evaluation_report_template.md`: 평가 보고서 템플릿

## 설치 의존성

추가 의존성 없이 Python 표준 라이브러리만 사용합니다.

## 실행 예시

```bash
cd <프로젝트 루트>
mkdir -p evaluation
# 이 폴더의 파일들을 evaluation/에 복사
python evaluation/evaluate_rag.py --dataset evaluation/evaluation_dataset.jsonl --base-url http://127.0.0.1:8000 --endpoint /chat --write-judge-inputs
```

API가 `/api/chat`이면:

```bash
python evaluation/evaluate_rag.py --dataset evaluation/evaluation_dataset.jsonl --base-url http://127.0.0.1:8000 --endpoint /api/chat --write-judge-inputs
```

## 생성 결과

- `evaluation_results.json`: 케이스별 상세 응답/체크 결과
- `evaluation_results.md`: 보고서에 붙이기 좋은 요약표
- `judge_inputs.jsonl`: LLM Judge에 넣을 프롬프트 입력
