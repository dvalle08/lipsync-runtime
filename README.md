# Talking Head Runtime

Independent local runtime for MuseTalk and SadTalker.

This project owns the infrastructure that does not belong in a client app:

- async gateway API
- Redis-backed durable queue
- Docker lifecycle control for GPU backends
- on-demand startup and idle shutdown of `musetalk-api` / `sadtalker-api`
- separate model, result, and cache volumes per backend
- explicit weight bootstrap jobs instead of first-run model downloads

## Services

- `api-gateway`: public HTTP API on `127.0.0.1:8000`
- `redis`: queue and job state
- `musetalk-api`: internal GPU backend, off by default
- `sadtalker-api`: internal GPU backend, off by default
- `weights-musetalk-init`: one-shot model bootstrap
- `weights-musetalk-cache-init`: one-shot MuseTalk cache bootstrap
- `weights-sadtalker-init`: one-shot model bootstrap

## Host prerequisites

- Docker Compose v2
- NVIDIA Container Toolkit configured for Docker
- Linux host with one NVIDIA GPU

## Quick start

1. Create a local env file:

```bash
cp .env.example .env
```

2. Build images:

```bash
docker compose -f deploy/compose.runtime.yaml build
```

3. Download weights into named volumes:

```bash
docker compose -f deploy/compose.runtime.yaml --profile bootstrap run --rm weights-musetalk-init
docker compose -f deploy/compose.runtime.yaml --profile bootstrap run --rm weights-musetalk-cache-init
docker compose -f deploy/compose.runtime.yaml --profile bootstrap run --rm weights-sadtalker-init
```

4. Start only Redis and the gateway:

```bash
docker compose -f deploy/compose.runtime.yaml up -d redis api-gateway
```

The gateway starts `musetalk-api` or `sadtalker-api` only when a job requires it.
For MuseTalk image uploads, the gateway pads odd image dimensions to the next even size before enqueueing the job so `ffmpeg` does not fail on still-image inputs.

## API

Submit a MuseTalk job:

```bash
curl -X POST http://127.0.0.1:8000/jobs/musetalk           -F 'source=@/absolute/path/avatar.mp4'           -F 'audio=@/absolute/path/driven.wav'           -F 'options_json={"fps":25,"use_cache":true}'
```

Submit a SadTalker job:

```bash
curl -X POST http://127.0.0.1:8000/jobs/sadtalker           -F 'source=@/absolute/path/avatar.png'           -F 'audio=@/absolute/path/driven.wav'           -F 'options_json={"size":256,"preprocess":"crop","enhancer":"gfpgan","still":true}'
```

Poll job status:

```bash
curl http://127.0.0.1:8000/jobs/<job_id>
```

Download the result:

```bash
curl -OJ http://127.0.0.1:8000/jobs/<job_id>/result
```

## Operational notes

- The gateway is intentionally bound to `127.0.0.1` because it has Docker control privileges.
- The worker serializes GPU jobs globally for a single-GPU host.
- MuseTalk uses a warm-loaded API server inside the backend container.
- SadTalker currently uses the official CLI inside a persistent backend container. The container stays warm, but the model process is not kept resident between jobs yet.
- Backends are stopped after `BACKEND_IDLE_TIMEOUT_SECONDS` with an empty queue.
