# sLLM LoRA/QLoRA 실험 산출물

## 1. 목적

본 폴더는 청년 정책 RAG 에이전트의 sLLM 파인튜닝 및 LoRA/QLoRA 평가 항목 대응을 위한 실험 산출물이다.

현재 서비스의 핵심 경로는 OpenAI API 기반 RAG, Chroma Vector DB, LangGraph ReAct workflow이다. 정책 정보는 최신성이 중요하므로, sLLM이 정책 내용을 직접 암기하도록 학습시키기보다 다음 보조 작업에 활용하는 방향으로 설계한다.

- 사용자 질문 의도 분류
- 사용자 조건 추출
- 자격 판단 응답 형식 정규화
- 마감 공고를 현재 신청 가능하다고 말하지 않는 안전 규칙 학습
- 한국어 정책 상담 말투 및 답변 템플릿 학습

## 2. 구성 파일

| 파일 | 설명 |
| --- | --- |
| `sample_lora_dataset.jsonl` | 정책 상담 instruction tuning 샘플 데이터 |
| `build_lora_dataset.py` | `evaluation/evaluation_dataset.jsonl`을 LoRA 학습 형식으로 변환 |
| `train_lora_qlora.py` | HuggingFace Transformers + PEFT 기반 LoRA/QLoRA 학습 예시 코드 |
| `lora_config_example.yaml` | base model, LoRA rank, QLoRA, Gradient Clipping 설정 예시 |

## 3. 데이터셋 생성

평가 질의셋에 `reference_answer`가 포함되어 있다면 다음 명령어로 학습용 JSONL을 만들 수 있다.

```bash
python training/build_lora_dataset.py \
  --input evaluation/evaluation_dataset.jsonl \
  --output training/lora_dataset.jsonl \
  --merge-sample
```

출력 형식은 다음과 같다.

```json
{
  "instruction": "사용자의 질문과 조건에 맞는 청년 정책을 출처 기반으로 안내하라.",
  "input": "질문: 2026년에 신청 가능한 창업지원 공고 추천해줘",
  "output": "2026년에 신청 가능한 창업지원 공고로 ..."
}
```

## 4. Dry-run

실제 GPU 학습 전에 설정과 데이터 파일 존재 여부만 확인할 수 있다.

```bash
python training/train_lora_qlora.py \
  --config training/lora_config_example.yaml \
  --dry-run
```

## 5. 실제 학습

실제 학습에는 CUDA GPU와 다음 패키지가 필요하다.

```bash
pip install transformers datasets accelerate peft bitsandbytes pyyaml
```

학습 실행 예시:

```bash
python training/train_lora_qlora.py --config training/lora_config_example.yaml
```

학습 결과는 기본적으로 다음 위치에 저장된다.

```text
training/outputs/policy-lora/
```

## 6. 적용 전략

본 프로젝트에서 sLLM/LoRA는 RAG를 대체하지 않는다.

| 영역 | 담당 |
| --- | --- |
| 최신 정책 검색 | RAG + Vector DB + 공식 출처 fallback |
| 출처 근거 확보 | source_url, application_url, metadata |
| 사용자 조건 추출 | sLLM 또는 LLM 보조 가능 |
| 자격 판단 문체/형식 정규화 | LoRA 튜닝 sLLM 보조 가능 |
| 답변 생성 템플릿 | LoRA 튜닝 sLLM 보조 가능 |

정책 내용을 sLLM에 직접 암기시키면 정책 만료, 신청 기간 변경, 공고 삭제 등 최신성 문제가 발생할 수 있다. 따라서 최신성은 RAG 계층이 담당하고, sLLM은 응답 형식과 판단 패턴을 보조하는 방식이 안전하다.

## 7. 평가 계획서 대응 포인트

- LoRA/QLoRA 기반 PEFT 학습 코드 골격 제공
- `max_grad_norm`을 통한 Gradient Clipping 설정 포함
- 4bit QLoRA 옵션 포함
- instruction tuning 데이터 생성 스크립트 제공
- 실제 서비스 적용 한계와 향후 확장 방향 문서화

## 8. 한계 및 향후 개선

- 현재 데이터셋은 샘플 규모이므로 실제 성능 향상을 기대하기 어렵다.
- 충분한 학습을 위해서는 수백~수천 개 이상의 고품질 정책 상담 instruction 데이터가 필요하다.
- 실제 학습 모델을 서비스에 투입하려면 별도 정량 평가가 필요하다.
- LM-Eval 또는 자체 RAG Judge 평가셋으로 파인튜닝 전후 성능 비교를 수행해야 한다.
