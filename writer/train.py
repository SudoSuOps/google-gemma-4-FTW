#!/usr/bin/env python3
"""
swarmGrant-Gemma4-31B — Grant Intelligence (Royal Jelly Cook)
=============================================================
Base: google/gemma-4-31B-it (4-bit QLoRA via BitsAndBytes)
Data: ~36,000 Deed Royal Jelly pairs (grants + finance + failure + DNA)
GPU:  RTX PRO 6000 Blackwell (96GB) — GPU 0

Gold Standard recipe: LR 1e-5, bf16 LoRA r=64 alpha=32, cosine, eff batch 32.

Architecture note: Gemma 4 is multimodal (Gemma4ForConditionalGeneration).
We train text-only via LoRA on the language model layers only.
Vision tower is frozen by default (no LoRA attached).

Run:
  python3 train_swarmgrant_gemma4_31b.py
"""
import os
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
# Disable torch inductor — Triton flex_attention backward exceeds Blackwell shared memory
os.environ["TORCHINDUCTOR_DISABLE"] = "1"

import json, random, time, torch
from transformers import (
    AutoModelForImageTextToText,
    AutoProcessor,
    BitsAndBytesConfig,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# ─── CONFIG ───────────────────────────────────────────
BASE_MODEL   = "google/gemma-4-31B-it"
DATA_FILE    = "/home/swarm/swarmwriter-nemotron70b/swarmwriter_full.jsonl"
OUTPUT_DIR   = "/home/swarm/swarmgrant-gemma4-31b"
ADAPTER_DIR  = os.path.join(OUTPUT_DIR, "lora-adapter")
SAMPLE_SIZE  = None  # Use all — entire dataset is curated Royal Jelly
MAX_LEN      = 4096
EPOCHS       = 3
LR           = 1e-5
BATCH_SIZE   = 2
GRAD_ACCUM   = 16        # eff batch = 2 * 16 = 32
LORA_R       = 64
LORA_ALPHA   = 32
SEED         = 42
# ──────────────────────────────────────────────────────

print("=" * 60)
print("  swarmGrant-Gemma4-31B — Royal Jelly Cook")
print(f"  {BASE_MODEL}")
print(f"  Deed Royal Jelly — all pairs | {EPOCHS} epochs | LR {LR}")
print(f"  QLoRA: r={LORA_R} alpha={LORA_ALPHA} | eff batch {BATCH_SIZE * GRAD_ACCUM}")
print("=" * 60)

# ─── 4-BIT QUANTIZATION CONFIG ──────────────────────
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

# ─── LOAD MODEL ─────────────────────────────────────
print("\n[1/5] Loading Gemma 4 31B (4-bit QLoRA)...")
model = AutoModelForImageTextToText.from_pretrained(
    BASE_MODEL,
    quantization_config=bnb_config,
    dtype=torch.bfloat16,
    attn_implementation="eager",  # avoid flex_attention Triton OOM on Blackwell
    device_map="auto",
)

print(f"  GPU: {torch.cuda.get_device_name(0)}")
print(f"  VRAM allocated: {torch.cuda.memory_allocated(0)/1e9:.1f} GB")

# Load processor (handles chat template for multimodal Gemma 4)
processor = AutoProcessor.from_pretrained(BASE_MODEL)
tokenizer = processor.tokenizer if hasattr(processor, 'tokenizer') else processor
print(f"  Processor: {type(processor).__name__}")
print(f"  Tokenizer: {type(tokenizer).__name__}")

# ─── PREPARE FOR QLORA ──────────────────────────────
print("\n[2/5] Preparing model for QLoRA training...")
model = prepare_model_for_kbit_training(
    model,
    use_gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
)

# LoRA config — target language model layers only (skip vision tower's Gemma4ClippableLinear)
lora_config = LoraConfig(
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    lora_dropout=0.05,
    target_modules=r".*language_model\.layers\.\d+\..*(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)",
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# ─── LOAD DATA (Deed Royal Jelly — all verified) ────
print(f"\n[3/5] Loading data from {DATA_FILE}...")
raw_pairs = []
with open(DATA_FILE) as f:
    for line in f:
        raw_pairs.append(json.loads(line))

print(f"  Deed Royal Jelly pairs: {len(raw_pairs):,}")

# Shuffle for training
random.seed(SEED)
random.shuffle(raw_pairs)

# Pre-tokenize with mm_token_type_ids (required by Gemma 4 multimodal arch)
def tokenize_pair(pair):
    msgs = pair["messages"]
    text = processor.apply_chat_template(
        msgs, tokenize=False, add_generation_prompt=False
    )
    encoded = tokenizer(
        text,
        max_length=MAX_LEN,
        truncation=True,
        padding=False,
        return_tensors=None,
    )
    # Gemma 4 requires mm_token_type_ids: 0=text, 1=image, 2=audio
    # All zeros for text-only training
    encoded["mm_token_type_ids"] = [0] * len(encoded["input_ids"])
    # Labels = input_ids for causal LM (SFTTrainer handles masking)
    encoded["labels"] = encoded["input_ids"].copy()
    return encoded

print("  Tokenizing pairs...")
tokenized = [tokenize_pair(p) for p in raw_pairs]

# Token length stats
sample_lens = [len(t["input_ids"]) for t in tokenized[:500]]
sample_lens.sort()
print(f"  Token stats (sample 500):")
print(f"    Mean: {sum(sample_lens)//len(sample_lens):,}")
print(f"    Median: {sample_lens[len(sample_lens)//2]:,}")
print(f"    P90: {sample_lens[int(len(sample_lens)*0.9)]:,}")
print(f"    P99: {sample_lens[int(len(sample_lens)*0.99)]:,}")
print(f"    Max: {max(sample_lens):,}")
truncated = sum(1 for l in sample_lens if l > MAX_LEN)
print(f"    Truncated at {MAX_LEN}: {truncated}/{len(sample_lens)} ({truncated/len(sample_lens)*100:.1f}%)")

# Train/eval split (95/5)
random.seed(SEED)
indices = list(range(len(tokenized)))
random.shuffle(indices)
split = int(0.95 * len(indices))
train_data = [tokenized[i] for i in indices[:split]]
eval_data = [tokenized[i] for i in indices[split:]]

train_dataset = Dataset.from_list(train_data)
eval_dataset = Dataset.from_list(eval_data)
print(f"  Train: {len(train_dataset):,} | Eval: {len(eval_dataset):,}")

# Custom collator that pads all fields including mm_token_type_ids
from dataclasses import dataclass
@dataclass
class Gemma4TextCollator:
    tokenizer: object
    max_length: int = MAX_LEN

    def __call__(self, features):
        # Separate mm_token_type_ids and labels before padding
        mm_ids = [f.pop("mm_token_type_ids") for f in features]
        labels = [f.pop("labels") for f in features]

        # Pad input_ids and attention_mask
        batch = self.tokenizer.pad(
            features,
            padding=True,
            max_length=self.max_length,
            return_tensors="pt",
        )

        # Pad mm_token_type_ids (pad with 0 = text type)
        max_len = batch["input_ids"].shape[1]
        batch["mm_token_type_ids"] = torch.tensor(
            [ids + [0] * (max_len - len(ids)) for ids in mm_ids]
        )

        # Pad labels (pad with -100 = ignore in loss)
        batch["labels"] = torch.tensor(
            [lab + [-100] * (max_len - len(lab)) for lab in labels]
        )

        return batch

# ─── TRAINING SETUP ──────────────────────────────────
total_steps = (len(train_dataset) // (BATCH_SIZE * GRAD_ACCUM)) * EPOCHS
eval_steps = max(total_steps // 10, 1)
warmup_steps = int(total_steps * 0.03)

print(f"\n[4/5] Training config:")
print(f"  Total steps: {total_steps:,}")
print(f"  Eval every: {eval_steps} steps")
print(f"  Warmup: {warmup_steps} steps")
print(f"  Eff batch size: {BATCH_SIZE * GRAD_ACCUM}")
print(f"  Max seq length: {MAX_LEN}")

config = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LR,
    lr_scheduler_type="cosine",
    warmup_steps=warmup_steps,
    bf16=True,
    logging_steps=10,
    eval_strategy="steps",
    eval_steps=eval_steps,
    save_strategy="steps",
    save_steps=eval_steps,
    save_total_limit=3,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    report_to="none",
    optim="adamw_8bit",
    seed=SEED,
    max_grad_norm=1.0,
    dataloader_pin_memory=False,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    remove_unused_columns=False,  # keep mm_token_type_ids
)

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    args=config,
    data_collator=Gemma4TextCollator(tokenizer=tokenizer),
)

# ─── COOK ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("  COOKING swarmGrant-Gemma4-31B — ROYAL JELLY")
print("=" * 60 + "\n")

start = time.time()
trainer.train()
elapsed = time.time() - start

# ─── SAVE ─────────────────────────────────────────────
print("\n[5/5] Saving adapter...")
trainer.save_model(ADAPTER_DIR)
tokenizer.save_pretrained(ADAPTER_DIR)

# Final eval
results = trainer.evaluate()

# VRAM report
peak_vram = 0
if torch.cuda.is_available():
    peak_vram = torch.cuda.max_memory_allocated() / 1e9

print("\n" + "=" * 60)
print("  swarmGrant-Gemma4-31B DONE")
print(f"  Eval loss: {results['eval_loss']:.4f}")
print(f"  Time: {elapsed/3600:.1f} hours")
print(f"  Peak VRAM: {peak_vram:.1f} GB")
print(f"  Adapter: {ADAPTER_DIR}")
print(f"  Next: merge + GGUF quantize → deploy")
print("=" * 60)

# Save metadata
meta = {
    "model": "swarmGrant-Gemma4-31B",
    "base": BASE_MODEL,
    "data": DATA_FILE,
    "sample_size": len(train_dataset) + len(eval_dataset),
    "data_quality": "deed royal jelly — all verified",
    "epochs": EPOCHS,
    "lr": LR,
    "lora_r": LORA_R,
    "lora_alpha": LORA_ALPHA,
    "max_len": MAX_LEN,
    "eval_loss": results["eval_loss"],
    "train_hours": round(elapsed / 3600, 2),
    "peak_vram_gb": round(peak_vram, 1),
    "train_pairs": len(train_dataset),
    "eval_pairs": len(eval_dataset),
    "quantization": "4-bit NF4 double-quant (BitsAndBytes)",
    "blackwell_workarounds": ["TORCHINDUCTOR_DISABLE=1", "attn_implementation=eager"],
}
with open(os.path.join(OUTPUT_DIR, "cook_meta.json"), "w") as f:
    json.dump(meta, f, indent=2)
print(f"  Metadata saved: {OUTPUT_DIR}/cook_meta.json")
