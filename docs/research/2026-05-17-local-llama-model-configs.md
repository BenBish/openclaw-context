---
title: Local llama-server Model Configurations
date: 2026-05-17
tags: [llm, llama-cpp, llama-swap, rocm, openclaw]
status: published
---

# Local llama-server Model Configurations

Known local model configurations used on the Strix Halo OpenClaw host.

## Runtime Pattern

llama-server runs inside the ROCm toolbox container:

```text
llama-rocm-7.2.2
```

llama-swap runs as a user systemd service and proxies OpenAI-compatible traffic from:

```text
http://localhost:8080/v1
```

to the active llama-server upstream, normally:

```text
http://127.0.0.1:12346
```

The active llama-swap config lives at:

```text
~/.config/llama-swap/config.yaml
```

OpenClaw model config lives at:

```text
~/.openclaw/openclaw.json
~/.openclaw/agents/main/agent/models.json
~/.openclaw/agents/tom/agent/models.json
~/.openclaw/agents/freddy/agent/models.json
```

## GPT-OSS 120B UD-Q4_K_XL

Status: previous OpenClaw model, replaced by Qwen3.6 27B plus Gemma fallback on 2026-05-22 because it did not deliver the expected performance gains.

Model path:

```text
/home/ben/AI/models/gpt-oss/UD-Q4_K_XL/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf
```

Command:

```bash
podman exec -d \
  -w /home/ben \
  -e HSA_OVERRIDE_GFX_VERSION=11.5.1 \
  llama-rocm-7.2.2 \
  sh -lc 'exec llama-server \
    -m /home/ben/AI/models/gpt-oss/UD-Q4_K_XL/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf \
    -ngl 99 \
    --n-cpu-moe 35 \
    -fa 1 \
    -c 131072 \
    -b 2048 \
    -ub 2048 \
    --no-warmup \
    --jinja \
    --temp 1.0 \
    --top-p 1.0 \
    --top-k 0 \
    --min-p 0.0 \
    --host 0.0.0.0 \
    --port 12346 \
    > /tmp/gpt-oss-120b-q4-cpumoe-12346.log 2>&1'
```

llama-swap model ID:

```text
gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf
```

OpenClaw model ID:

```text
local-llama/gpt-oss-120b-UD-Q4_K_XL-00001-of-00002.gguf
```

Notes:

- Requires `--n-cpu-moe 35`.
- Requires `--no-warmup` for reliable startup in the observed setup.
- Keep context at `131072` for OpenClaw.
- Leave KV cache at default f16 unless memory pressure requires re-testing q8 KV.

## GPT-OSS 120B UD-Q6_K_XL

Status: tested, not selected as the active OpenClaw model.

Model path:

```text
/home/ben/AI/models/gpt-oss/UD-Q6_K_XL/gpt-oss-120b-UD-Q6_K_XL-00001-of-00002.gguf
```

Command tested:

```bash
podman exec -d \
  -w /home/ben \
  -e HSA_OVERRIDE_GFX_VERSION=11.5.1 \
  llama-rocm-7.2.2 \
  sh -lc 'exec llama-server \
    -m /home/ben/AI/models/gpt-oss/UD-Q6_K_XL/gpt-oss-120b-UD-Q6_K_XL-00001-of-00002.gguf \
    -ngl 99 \
    --n-cpu-moe 35 \
    -fa 1 \
    -c 131072 \
    -b 2048 \
    -ub 2048 \
    --no-warmup \
    --jinja \
    --temp 1.0 \
    --top-p 1.0 \
    --top-k 0 \
    --min-p 0.0 \
    --host 0.0.0.0 \
    --port 12347 \
    > /tmp/gpt-oss-120b-q6-solo-12347.log 2>&1'
```

Notes:

- Starts successfully with the same `--n-cpu-moe 35` and `--no-warmup` strategy as Q4.
- Uses about 61 GiB RSS in the observed solo run.
- Short benchmark was similar to Q4, not clearly better.
- Did not improve enough on OpenClaw command/tool behavior to justify replacing Q4.

## GLM-4.7-Flash UD-Q8_K_XL

Status: tested as a fast alternate, not selected as the active OpenClaw model.

Model path:

```text
/home/ben/AI/models/GLM-4.7-Flash-GGUF/GLM-4.7-Flash-UD-Q8_K_XL.gguf
```

Command tested:

```bash
podman exec -d \
  -w /home/ben \
  -e HSA_OVERRIDE_GFX_VERSION=11.5.1 \
  llama-rocm-7.2.2 \
  sh -lc 'exec llama-server \
    -m /home/ben/AI/models/GLM-4.7-Flash-GGUF/GLM-4.7-Flash-UD-Q8_K_XL.gguf \
    -ngl 99 \
    -fa 1 \
    -c 131072 \
    -b 2048 \
    -ub 2048 \
    --no-warmup \
    --jinja \
    --reasoning off \
    --temp 0.6 \
    --top-p 0.95 \
    --host 0.0.0.0 \
    --port 12347 \
    > /tmp/glm-4.7-flash-q8-12347.log 2>&1'
```

Notes:

- Starts successfully with 131k context.
- Mostly offloads to VRAM; observed process RSS was about 2 GiB, with about 33 GiB ROCm model buffer and about 6.8 GiB KV buffer.
- Much faster than GPT-OSS on short exact-output prompts.
- Needs stricter system prompting to avoid Markdown fences.
- In an OpenClaw-specific command prompt, it used system-level `systemctl` instead of `systemctl --user`, so it needs more agent-prompt validation before being considered as the main model.

## GPT-OSS 120B F16

Status: downloaded and tested, but did not successfully finish startup with the initial command.

Model path:

```text
/home/ben/AI/models/gpt-oss/gpt-oss-120b-F16.gguf
```

Initial command tested:

```bash
llama-server \
  -m /home/ben/AI/models/gpt-oss/gpt-oss-120b-F16.gguf \
  -ngl 999 \
  -fa 1 \
  -c 131072 \
  -b 2048 \
  -ub 1024 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --jinja \
  --temp 0.35 \
  --top-p 0.95 \
  --min-p 0.02 \
  --host 0.0.0.0 \
  --port 12346
```

Observed result:

```json
{"error":{"message":"Loading model","type":"unavailable_error","code":503}}
```

Notes:

- The model bound the port but never reached ready state.
- A future F16 test should use the same strategy that fixed Q4: `--n-cpu-moe 35`, `--no-warmup`, and no KV quantization for the first boot.

## Qwen3-Coder 30B A3B Instruct

Status: previous OpenClaw primary model.

Model path:

```text
/home/ben/AI/models/Qwen3-Coder-30B-A3B-Instruct-GGUF/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf
```

Command:

```bash
cd /home/ben && llama-server \
  -m AI/models/Qwen3-Coder-30B-A3B-Instruct-GGUF/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf \
  -ngl 99 \
  -fa 1 \
  -c 65536 \
  --temp 0.25 \
  --top-p 0.9 \
  --top-k 20 \
  --min-p 0.05 \
  --jinja \
  --port 12346 \
  --host 0.0.0.0 \
  > /tmp/qwen3-coder-12346.log 2>&1
```

llama-swap model ID:

```text
Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf
```

OpenClaw model ID:

```text
local-llama/Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf
```

Notes:

- Worked as a 64k context coding-capable model.
- Replaced because OpenClaw needed a larger main model and stronger long-context behavior.

## Qwen3.6 35B A3B

Status: previous local model used before Qwen3-Coder.

Model ID:

```text
Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf
```

Known configuration from earlier notes:

```bash
llama-server \
  -m AI/models/Qwen3.6-35B-A3B/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf \
  -ngl 99 \
  -fa 1 \
  -c 131072 \
  --temp 0.6 \
  --top-p 0.95 \
  --jinja \
  --port 12346 \
  --host 0.0.0.0
```

Notes:

- Used with 131k context.
- Eventually superseded by Qwen3-Coder and then GPT-OSS.

## Qwen3.6 27B

Status: current OpenClaw primary model.

Model path:

```text
/home/ben/AI/models/Qwen3.6-27B-GGUF/Qwen3.6-27B-UD-Q4_K_XL.gguf
```

Command:

```bash
podman exec -d \
  -w /home/ben \
  -e HSA_OVERRIDE_GFX_VERSION=11.5.1 \
  llama-rocm-7.2.2 \
  sh -lc 'exec llama-server \
    -m /home/ben/AI/models/Qwen3.6-27B-GGUF/Qwen3.6-27B-UD-Q4_K_XL.gguf \
    -ngl 99 \
    -fa 1 \
    -c 131072 \
    -b 2048 \
    -ub 2048 \
    --no-warmup \
    --jinja \
    --reasoning off \
    --temp 0.6 \
    --top-p 0.95 \
    --host 0.0.0.0 \
    --port 12346 \
    > /tmp/qwen3.6-27b-12346.log 2>&1'
```

llama-swap model ID:

```text
Qwen3.6-27B-UD-Q4_K_XL.gguf
```

OpenClaw model ID:

```text
local-llama/Qwen3.6-27B-UD-Q4_K_XL.gguf
```

Notes:

- Runs as the primary local model on port `12346`.
- Uses 131k context for OpenClaw compatibility.

## Gemma 4 26B A4B

Status: current OpenClaw fallback model.

Model path:

```text
/home/ben/AI/models/gemma-4-26B-A4B/gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf
```

Command:

```bash
podman exec -d \
  -w /home/ben \
  -e HSA_OVERRIDE_GFX_VERSION=11.5.1 \
  llama-rocm-7.2.2 \
  sh -lc 'exec llama-server \
    -m /home/ben/AI/models/gemma-4-26B-A4B/gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf \
    -ngl 99 \
    -fa 1 \
    -c 32768 \
    --no-warmup \
    --jinja \
    --reasoning off \
    --host 0.0.0.0 \
    --port 12345 \
    > /tmp/gemma-4-26b-a4b-12345.log 2>&1'
```

llama-swap model ID:

```text
gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf
```

OpenClaw model ID:

```text
local-llama/gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf
```

Notes:

- Runs as the fallback local model on port `12345`.
- Uses 32k context.

## Standard Verification

Health:

```bash
curl http://127.0.0.1:12346/health
curl http://127.0.0.1:12345/health
```

llama-swap models:

```bash
curl http://127.0.0.1:8080/v1/models
```

OpenClaw models:

```bash
openclaw models list
```

Services:

```bash
systemctl --user status llama-swap.service --no-pager
systemctl --user status openclaw-gateway.service --no-pager
```
