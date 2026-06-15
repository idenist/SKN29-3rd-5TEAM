# sLLM LoRA/QLoRA 실험 모듈

이 폴더는 청년 정책 RAG 서비스의 sLLM 파인튜닝 평가 항목 대응을 위한 실험 코드입니다.
운영 서비스의 메인 LLM을 바로 교체하기 위한 목적이 아니라, 정책 QA 데이터를 instruction format으로 변환하고 LoRA/QLoRA 기반 PEFT 학습 및 간이 평가를 수행하기 위한 구조입니다.

## 폴더 구조

```text
sllm/
├── scripts/
│   ├── prepare_sllm_dataset.py
│   ├── train_lora.py
│   ├── evaluate_sllm.py
│   └── run_lm_eval.py
├── configs/
│   ├── lora_config.yaml
│   ├── qlora_config.yaml
│   └── generation_config.yaml
└── data/                 # prepare_sllm_dataset.py 실행 시 생성
```

## 1. 데이터 생성

직접 손으로 만들 필요 없이 기존 전처리 결과에서 생성할 수 있습니다.

```bash
python sllm/scripts/prepare_sllm_dataset.py \
  --input data/processed/opportunities.json \
  --output-dir sllm/data \
  --max-samples 1000 \
  --eval-ratio 0.1
```

대체 입력 파일:

```bash
python sllm/scripts/prepare_sllm_dataset.py --input data/processed/policies.json --output-dir sllm/data
python sllm/scripts/prepare_sllm_dataset.py --input data/processed/opportunity_chunks.jsonl --output-dir sllm/data
```

## 2. LoRA 학습

```bash
python sllm/scripts/train_lora.py --config sllm/configs/lora_config.yaml
```

## 3. QLoRA 학습

```bash
python sllm/scripts/train_lora.py --config sllm/configs/qlora_config.yaml
```

## 4. 간이 평가

```bash
python sllm/scripts/evaluate_sllm.py \
  --model sllm/outputs/lora_policy_qa \
  --eval-file sllm/data/policy_qa_eval_sample.jsonl \
  --output sllm/evaluation/sllm_eval_results.json
```

## 5. LM-Eval 실행 예시

```bash
python sllm/scripts/run_lm_eval.py \
  --model hf \
  --model-args pretrained=sllm/outputs/lora_policy_qa \
  --tasks kobest_boolq,kobest_hellaswag \
  --output-path sllm/evaluation/lm_eval_results.json
```

## 보고서 작성 포인트

- 운영 서비스는 안정성을 위해 OpenAI 기반 RAG를 사용했다.
- sLLM은 별도 실험 모듈로 구성했다.
- 정책 데이터를 instruction tuning 형식으로 변환했다.
- LoRA/QLoRA, gradient checkpointing, gradient clipping, 4bit quantization 설정을 포함했다.
- 시간과 GPU 제약으로 실제 서비스 교체는 향후 과제로 남겼다.
