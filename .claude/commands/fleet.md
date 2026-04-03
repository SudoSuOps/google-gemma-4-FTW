Check or manage the Swarm & Bee hardware fleet: $ARGUMENTS

You are the Fleet Manager. You monitor and manage all NVIDIA silicon across the swarm.

## Fleet Inventory

| Node | IP | Hardware | Role |
|------|-----|----------|------|
| swarmrails | localhost | 2x RTX PRO 6000 Blackwell (96GB) + Xeon w9-3475X | Training + API |
| whale | 192.168.0.99 | RTX 3090 (24GB) + Ryzen 9 5900X | Inference |
| sigedge | 192.168.0.79 | Jetson Orin Nano 8GB | Edge judge + inference |
| bee (zima) | 192.168.0.70 | Intel N150 16GB | SwarmJelly 4B |
| zima-lite | 192.168.0.173 | Celeron N3450 8GB | Web host (swarmandbee.ai) |
| zima-edge-1 | 192.168.0.230 | Intel N150 + T1000 (pending) | Edge inference |

## Commands

### "status" — Full fleet health check
- Ping each node
- Check GPU utilization where applicable
- Report: online/offline, GPU load, VRAM, temperature

### "deploy <model> <node>" — Deploy a model to a node
- Copy GGUF to target node
- Set up ollama/llama.cpp serving
- Verify inference works

### "benchmark <node>" — Run inference benchmark
- Measure tok/s on the target node
- Report latency, throughput, VRAM usage

## SSH Credentials
- whale: swarm@192.168.0.99
- sigedge: sigedge@192.168.0.79
- bee: dev@192.168.0.70 pass:mack
- zima-lite: bee@192.168.0.173 pass:mack
- zima-edge-1: dev@192.168.0.230 pass:mack
