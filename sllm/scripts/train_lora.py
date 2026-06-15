"""
LoRA/QLoRA 학습 스크립트.

사용 예:
python sllm/scripts/train_lora.py --config sllm/configs/lora_config.yaml
python sllm/scripts/train_lora.py --config sllm/configs/qlora_config.yaml

필요 패키지:
pip install transformers datasets peft accelerate bitsandbytes pyyaml sentencepiece
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import torch
import yaml
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
    set_seed,
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_messages(example: dict[str, Any], tokenizer) -> str:
    if "messages" in example and example["messages"]:
        try:
            return tokenizer.apply_chat_template(
                example["messages"],
                tokenize=False,
                add_generation_prompt=False,
            )
        except Exception:
            pass

    instruction = example.get("instruction", "")
    input_text = example.get("input", "")
    output = example.get("output", "")
    return (
        "<|user|>\n"
        f"{instruction}\n\n{input_text}\n"
        "<|assistant|>\n"
        f"{output}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_yaml(args.config)
    set_seed(int(cfg.get("seed", 42)))

    model_name = cfg["model_name_or_path"]
    train_file = cfg["train_file"]
    eval_file = cfg.get("eval_file")
    output_dir = cfg.get("output_dir", "sllm/outputs/lora_policy_qa")
    max_seq_length = int(cfg.get("max_seq_length", 1024))
    use_qlora = bool(cfg.get("use_qlora", False))

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    if use_qlora:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=cfg.get("bnb_4bit_quant_type", "nf4"),
            bnb_4bit_compute_dtype=getattr(torch, cfg.get("bnb_4bit_compute_dtype", "bfloat16")),
            bnb_4bit_use_double_quant=bool(cfg.get("bnb_4bit_use_double_quant", True)),
        )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        device_map=cfg.get("device_map", "auto"),
        torch_dtype=getattr(torch, cfg.get("torch_dtype", "bfloat16")),
        quantization_config=quantization_config,
    )

    if use_qlora:
        model = prepare_model_for_kbit_training(model)

    lora_cfg = LoraConfig(
        r=int(cfg.get("lora_r", 16)),
        lora_alpha=int(cfg.get("lora_alpha", 32)),
        lora_dropout=float(cfg.get("lora_dropout", 0.05)),
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=cfg.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj"]),
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    data_files = {"train": train_file}
    if eval_file:
        data_files["validation"] = eval_file
    dataset = load_dataset("json", data_files=data_files)

    def tokenize_fn(example):
        text = format_messages(example, tokenizer)
        tokenized = tokenizer(
            text,
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    tokenized = dataset.map(tokenize_fn, remove_columns=dataset["train"].column_names)

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=float(cfg.get("num_train_epochs", 1)),
        per_device_train_batch_size=int(cfg.get("per_device_train_batch_size", 1)),
        per_device_eval_batch_size=int(cfg.get("per_device_eval_batch_size", 1)),
        gradient_accumulation_steps=int(cfg.get("gradient_accumulation_steps", 8)),
        learning_rate=float(cfg.get("learning_rate", 2e-4)),
        weight_decay=float(cfg.get("weight_decay", 0.0)),
        warmup_ratio=float(cfg.get("warmup_ratio", 0.03)),
        lr_scheduler_type=cfg.get("lr_scheduler_type", "cosine"),
        logging_steps=int(cfg.get("logging_steps", 10)),
        save_steps=int(cfg.get("save_steps", 100)),
        eval_steps=int(cfg.get("eval_steps", 100)),
        evaluation_strategy="steps" if eval_file else "no",
        save_total_limit=int(cfg.get("save_total_limit", 2)),
        bf16=bool(cfg.get("bf16", True)),
        fp16=bool(cfg.get("fp16", False)),
        gradient_checkpointing=bool(cfg.get("gradient_checkpointing", True)),
        max_grad_norm=float(cfg.get("max_grad_norm", 1.0)),
        report_to=cfg.get("report_to", "none"),
        remove_unused_columns=False,
    )

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized.get("validation"),
        data_collator=collator,
    )

    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"LoRA adapter saved to: {output_dir}")


if __name__ == "__main__":
    main()
