# Talking Head Runtime

Local runtime for **MuseTalk** and **SadTalker**: a small **FastAPI gateway**, **Redis** queue, and **GPU backends** that start on demand and stop when idle. Model files are installed with explicit **bootstrap** jobs (named Docker volumes), not on first inference.

## Prerequisites

- Linux, one NVIDIA GPU  
- Docker Compose v2  
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for Docker  

## Quick start

Run commands from the **repository root**. HTTP is **`127.0.0.1:${APP_PORT:-8000}`** (default **8000**).

```bash
cp .env.example .env
docker compose -f deploy/compose.runtime.yaml build
docker compose -f deploy/compose.runtime.yaml --profile bootstrap run --rm weights-musetalk-init
docker compose -f deploy/compose.runtime.yaml --profile bootstrap run --rm weights-musetalk-cache-init
docker compose -f deploy/compose.runtime.yaml --profile bootstrap run --rm weights-sadtalker-init
docker compose -f deploy/compose.runtime.yaml up -d redis api-gateway
curl http://127.0.0.1:8000/health/ready
```

After this, only **redis** and **api-gateway** run. The gateway starts **`musetalk-api`** or **`sadtalker-api`** when a job needs them.

Re-running bootstrap is safe: existing files in the volumes are **skipped** (see `docker/init/download_weights.py`).

## What runs where

| Piece | Role |
|--------|------|
| **api-gateway** | HTTP API, job storage, queue worker, `docker compose` to start/stop backends |
| **redis** | Queue + job JSON |
| **musetalk-api** / **sadtalker-api** | GPU inference (Compose **profiles**; not started by `up` alone until a job triggers them) |
| **weights-*-init** | One-shot downloads into **models** / **cache** volumes (`--profile bootstrap`) |

## API examples

**MuseTalk** (image or video + audio):

```bash
curl -X POST http://127.0.0.1:8000/jobs/musetalk \
  -F 'source=@/absolute/path/avatar.mp4' \
  -F 'audio=@/absolute/path/driven.wav' \
  -F 'options_json={"fps":25,"use_cache":true}'
```

**SadTalker** (image + audio):

```bash
curl -X POST http://127.0.0.1:8000/jobs/sadtalker \
  -F 'source=@/absolute/path/avatar.png' \
  -F 'audio=@/absolute/path/driven.wav' \
  -F 'options_json={"size":256,"preprocess":"crop","enhancer":"gfpgan","still":true}'
```

**Status and result:**

```bash
curl http://127.0.0.1:8000/jobs/<job_id>
curl -OJ http://127.0.0.1:8000/jobs/<job_id>/result
```

## Behavior notes

- Gateway listens on **localhost only** — it mounts the Docker socket to control backends.  
- One worker processes jobs **one at a time** on a single-GPU machine; switching engines **stops** the other backend first.  
- MuseTalk: models stay loaded in the backend process. **MuseTalk image** inputs may be padded to **even** width/height before the job is queued (avoids common `ffmpeg` failures).  
- SadTalker: runs the upstream **CLI** per job inside a long-lived container.  
- Idle backends are stopped after **`BACKEND_IDLE_TIMEOUT_SECONDS`** (see `.env.example`).  

## Layout

- `src/talking_head_runtime/` — gateway app  
- `deploy/compose.runtime.yaml` — stack definition  
- `docker/` — images (gateway, backends, bootstrap)  
- `weights/*.manifest.json` — bootstrap file lists  

More copy-paste commands: `dev/smoke/commands_2.md`.
