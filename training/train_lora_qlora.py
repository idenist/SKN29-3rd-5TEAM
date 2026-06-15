"""
HuggingFace Transformers + PEFT 기반 LoRA/QLoRA 학습 예시 코드.

주의:
- 이 코드는 평가 산출물 대응 및 실험용 골격이다.
- 실제 실행에는 CUDA GPU, transformers, datasets, peft, accelerate, bitsandbytes 설치가 필요하다.
- 정책 내용 자체를 모델에 암기시키는 것이 아니라, 정책 상담 응답 형식과 판단 패턴을 튜닝하는 목적이다.

실행 예시:
  python training/train_lora_qlora.py --config training/lora_config_example.yaml
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def load_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"config 파일을 찾을 수 없습니다: {config_path}")

    if config_path.suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML이 설치되어 있지 않습니다. pip install pyyaml")
        with config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def format_instruction(example: dict[str, Any]) -> str:
    instruction = str(example.get("instruction", "")).strip()
    input_text = str(example.get("input", "")).strip()
    output = str(example.get("output", "")).strip()

    return (
        "### Instruction:\n"
        f"{instruction}\n\n"
        "### Input:\n"
        f"{input_text}\n\n"
        "### Response:\n"
        f"{output}"
    )


def train(config: dict[str, Any]) -> None:
    # 무거운 라이브러리는 실제 train 호출 시점에 import한다.
    from datasets import load_dataset
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )
    import torch

    base_model = config["base_model"]
    dataset_path = config["dataset_path"]
    output_dir = config["output_dir"]
    max_seq_length = int(config.get("max_seq_length", 1024))

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    use_4bit = bool(config.get("use_4bit", True))
    quantization_config = None

    if use_4bit:
        compute_dtype = getattr(torch, config.get("bnb_4bit_compute_dtype", "float16"))
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_quant_type=config.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_use_double_quant=bool(config.get("bnb_4bit_use_double_quant", True)),
        )

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )

    if use_4bit:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=int(config.get("lora_r", 16)),
        lora_alpha=int(config.get("lora_alpha", 32)),
        lora_dropout=float(config.get("lora_dropout", 0.05)),
        target_modules=config.get("target_modules") or ["q_proj", "v_proj"],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)

    dataset = load_dataset("json", data_files=dataset_path, split="train")

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        texts = []
        for i in range(len(batch["instruction"])):
            texts.append(
                format_instruction(
                    {
                        "instruction": batch["instruction"][i],
                        "input": batch["input"][i],
                        "output": batch["output"][i],
                    }
                )
            )
        return tokenizer(
            texts,
            truncation=True,
            max_length=max_seq_length,
            padding="max_length",
        )

    tokenized = dataset.map(tokenize, batched=True, remove_columns=dataset.column_names)

    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=int(config.get("train_batch_size", 1)),
        gradient_accumulation_steps=int(config.get("gradient_accumulation_steps", 8)),
        num_train_epochs=float(config.get("num_train_epochs", 2)),
        learning_rate=float(config.get("learning_rate", 2e-4)),
        warmup_ratio=float(config.get("warmup_ratio", 0.03)),
        weight_decay=float(config.get("weight_decay", 0.01)),
        max_grad_norm=float(config.get("max_grad_norm", 0.3)),
        logging_steps=int(config.get("logging_steps", 5)),
        save_steps=int(config.get("save_steps", 50)),
        fp16=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    print(f"LoRA adapter 저장 완료: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="training/lora_config_example.yaml")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="설정과 데이터 파일 존재 여부만 확인하고 학습은 실행하지 않음",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    dataset_path = Path(config["dataset_path"])

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"학습 데이터가 없습니다: {dataset_path}\n"
            "먼저 build_lora_dataset.py를 실행하거나 sample_lora_dataset.jsonl을 확인하세요."
        )

    if args.dry_run:
        print("dry-run 성공")
        print(json.dumps(config, ensure_ascii=False, indent=2))
        print(f"dataset_path: {dataset_path}")
        return

    train(config)


if __name__ == "__main__":
    main()
