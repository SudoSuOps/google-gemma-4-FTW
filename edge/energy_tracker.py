#!/usr/bin/env python3
"""
SwarmEnergy — Real-time energy economics tracker.

Energy is the proof of work. Every deed has a cost-to-weigh in watts.
Every model has a cost-to-cook in kWh. Every pound has an energy cost.
The weight costs energy. The energy proves the work. Price per pound.

This tracks:
- Real-time GPU power draw (via nvidia-smi)
- Cost per deed (tribunal energy / deeds per hour)
- Cost per training step (cook energy / steps)
- Fleet total power and cost
- Energy efficiency trends over time

Usage:
    python3 energy_tracker.py                    # Print current snapshot
    python3 energy_tracker.py --json             # JSON output
    DATABASE_URL="..." python3 energy_tracker.py --record  # Record to DB
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


KWH_RATE = float(os.environ.get("ELECTRICITY_RATE", "0.10"))


def get_gpu_power():
    """Get real-time GPU power and clock data from nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,power.draw,temperature.gpu,utilization.gpu,memory.used,memory.total,clocks.gr,clocks.mem,clocks.max.gr,clocks.max.mem,power.limit,utilization.memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                gpu = {
                    "index": int(parts[0]),
                    "name": parts[1],
                    "power_w": float(parts[2]),
                    "temp_c": int(parts[3]),
                    "util_pct": int(parts[4]),
                    "vram_used_mb": int(parts[5]),
                    "vram_total_mb": int(parts[6]),
                }
                if len(parts) >= 13:
                    gpu["core_mhz"] = int(parts[7])
                    gpu["mem_mhz"] = int(parts[8])
                    gpu["core_max_mhz"] = int(parts[9])
                    gpu["mem_max_mhz"] = int(parts[10])
                    gpu["power_limit_w"] = float(parts[11])
                    gpu["mem_util_pct"] = int(parts[12])
                    gpu["core_pct"] = round(gpu["core_mhz"] / max(gpu["core_max_mhz"], 1) * 100, 1)
                    gpu["mem_pct"] = round(gpu["mem_mhz"] / max(gpu["mem_max_mhz"], 1) * 100, 1)
                    gpu["throttled"] = gpu["power_w"] >= gpu["power_limit_w"] * 0.98
                gpus.append(gpu)
        return gpus
    except Exception:
        return []


def get_fleet_energy():
    """Calculate full fleet energy snapshot."""
    gpus = get_gpu_power()

    # Fixed estimates for non-GPU components
    fleet = {
        "gpus": gpus,
        "cpu_w": 250,       # Xeon w9-3475X under load
        "edge_w": 50,       # T1000 + deed recorder
        "whale_w": 200,     # RTX 3090 estimated (can't query remotely easily)
        "nas_w": 40,        # Synology DS1525+
    }

    gpu_total = sum(g["power_w"] for g in gpus)
    fleet_total = gpu_total + fleet["cpu_w"] + fleet["edge_w"] + fleet["whale_w"] + fleet["nas_w"]

    fleet["gpu_total_w"] = round(gpu_total, 1)
    fleet["fleet_total_w"] = round(fleet_total, 1)
    fleet["fleet_kw"] = round(fleet_total / 1000, 3)

    # Cost
    fleet["cost_per_hour"] = round(fleet["fleet_kw"] * KWH_RATE, 4)
    fleet["cost_per_day"] = round(fleet["cost_per_hour"] * 24, 2)
    fleet["cost_per_month"] = round(fleet["cost_per_day"] * 30, 2)

    # Per-deed cost (tribunal energy / throughput)
    tribunal_w = sum(g["power_w"] for g in gpus if g["index"] == 1) + fleet["whale_w"] + fleet["edge_w"] + fleet["cpu_w"] / 2
    pairs_per_hour = 767  # measured rate
    if pairs_per_hour > 0:
        wh_per_deed = tribunal_w / pairs_per_hour
        fleet["cost_per_deed"] = round((wh_per_deed / 1000) * KWH_RATE, 8)
        fleet["wh_per_deed"] = round(wh_per_deed, 4)
        fleet["energy_per_1000"] = round(wh_per_deed * 1000, 2)
    else:
        fleet["cost_per_deed"] = 0
        fleet["wh_per_deed"] = 0

    # Per training step
    cook_w = sum(g["power_w"] for g in gpus if g["index"] == 0)
    seconds_per_step = 64
    wh_per_step = cook_w * (seconds_per_step / 3600)
    fleet["cost_per_step"] = round((wh_per_step / 1000) * KWH_RATE, 8)
    fleet["wh_per_step"] = round(wh_per_step, 2)

    # Efficiency metrics
    fleet["watts_per_deed"] = round(tribunal_w, 1)
    fleet["pairs_per_watt"] = round(pairs_per_hour / max(tribunal_w, 1), 6)
    fleet["pairs_per_kwh"] = round(pairs_per_hour / max(tribunal_w / 1000, 0.001), 1)

    fleet["timestamp"] = datetime.now(timezone.utc).isoformat()
    fleet["kwh_rate"] = KWH_RATE

    return fleet


def print_snapshot(fleet):
    print("═══ SWARM ENERGY — LIVE SNAPSHOT ═══")
    print(f"Timestamp: {fleet['timestamp'][:19]}")
    print()
    print("GPUs:")
    for g in fleet["gpus"]:
        bar = "█" * int(g["util_pct"] / 5) + "░" * (20 - int(g["util_pct"] / 5))
        print(f"  GPU{g['index']}: {g['power_w']:>6.1f}W  {g['temp_c']}°C  [{bar}] {g['util_pct']}%  {g['name'][:30]}")
    print()
    # MINER — Clock analysis
    print("MINER (clock settings):")
    for g in fleet["gpus"]:
        if "core_mhz" in g:
            throttle = "⚠ THROTTLED" if g.get("throttled") else "✓ OK"
            print(f"  GPU{g['index']}: Core {g['core_mhz']:>5} MHz ({g['core_pct']:>4.1f}% of {g['core_max_mhz']}) | "
                  f"Mem {g['mem_mhz']:>5} MHz ({g['mem_pct']:>4.1f}% of {g['mem_max_mhz']}) | "
                  f"PL {g['power_limit_w']:.0f}W | Mem util {g['mem_util_pct']}% | {throttle}")
    print()
    print(f"Fleet total:     {fleet['fleet_total_w']:>7.1f}W ({fleet['fleet_kw']:.3f} kW)")
    print(f"Cost/hour:       ${fleet['cost_per_hour']:.4f}")
    print(f"Cost/day:        ${fleet['cost_per_day']:.2f}")
    print(f"Cost/month:      ${fleet['cost_per_month']:.2f}")
    print()
    print("DEED ECONOMICS:")
    print(f"  Energy/deed:   {fleet['wh_per_deed']:.4f} Wh")
    print(f"  Cost/deed:     ${fleet['cost_per_deed']:.6f}")
    print(f"  Cost/1000:     ${fleet['cost_per_deed']*1000:.4f}")
    print(f"  Pairs/kWh:     {fleet['pairs_per_kwh']:.0f}")
    print()
    print("COOK ECONOMICS:")
    print(f"  Energy/step:   {fleet['wh_per_step']:.2f} Wh")
    print(f"  Cost/step:     ${fleet['cost_per_step']:.6f}")
    print(f"  Full cook:     ${fleet['cost_per_step']*3204:.2f} (3,204 steps)")


if __name__ == "__main__":
    fleet = get_fleet_energy()
    if "--json" in sys.argv:
        print(json.dumps(fleet, indent=2))
    else:
        print_snapshot(fleet)
