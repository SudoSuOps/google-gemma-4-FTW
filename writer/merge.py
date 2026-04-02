#!/usr/bin/env python3
"""
Adapter Merge + GGUF Export
===========================
Merges LoRA adapter into base model and exports GGUF for edge deployment.

Usage:
    python merge.py --adapter /path/to/lora-adapter --output /path/to/merged --quant Q4_K_M
"""
import argparse
import os
import subprocess


def merge_adapter(base_model, adapter_path, output_path):
    """Merge LoRA adapter into base model."""
    from transformers import AutoModelForImageTextToText, AutoProcessor
    from peft import PeftModel
    import torch

    print(f"[merge] Loading base: {base_model}")
    model = AutoModelForImageTextToText.from_pretrained(
        base_model,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
    )

    print(f"[merge] Loading adapter: {adapter_path}")
    model = PeftModel.from_pretrained(model, adapter_path)

    print(f"[merge] Merging...")
    model = model.merge_and_unload()

    print(f"[merge] Saving merged model: {output_path}")
    os.makedirs(output_path, exist_ok=True)
    model.save_pretrained(output_path)

    processor = AutoProcessor.from_pretrained(base_model)
    processor.save_pretrained(output_path)

    print(f"[merge] Done: {output_path}")
    return output_path


def export_gguf(model_path, output_dir, quant="Q4_K_M"):
    """Export to GGUF using llama.cpp."""

    gguf_name = f"swarmgrant-gemma4-31b-{quant.lower()}.gguf"
    gguf_path = os.path.join(output_dir, gguf_name)

    print(f"[gguf] Converting to GGUF ({quant})...")

    # Step 1: Convert to GGUF F16
    f16_path = os.path.join(output_dir, "model-f16.gguf")
    subprocess.run([
        "python3", "llama.cpp/convert_hf_to_gguf.py",
        model_path,
        "--outfile", f16_path,
        "--outtype", "f16",
    ], check=True)

    # Step 2: Quantize
    subprocess.run([
        "llama.cpp/build/bin/llama-quantize",
        f16_path,
        gguf_path,
        quant,
    ], check=True)

    # Clean up F16
    os.remove(f16_path)

    size_gb = os.path.getsize(gguf_path) / 1e9
    print(f"[gguf] Exported: {gguf_path} ({size_gb:.1f} GB)")
    return gguf_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge + GGUF Export")
    parser.add_argument("--base", default="google/gemma-4-31B-it", help="Base model")
    parser.add_argument("--adapter", required=True, help="LoRA adapter path")
    parser.add_argument("--output", required=True, help="Output directory for merged model")
    parser.add_argument("--quant", default="Q4_K_M", help="GGUF quantization (Q4_K_M, Q8_0, etc)")
    parser.add_argument("--skip-merge", action="store_true", help="Skip merge, only export GGUF")
    args = parser.parse_args()

    if not args.skip_merge:
        merge_adapter(args.base, args.adapter, args.output)

    export_gguf(args.output, args.output, args.quant)
