from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, "/opt/musetalk")
sys.path.insert(0, "/srv/adapter")

from musetalk_api_server import MuseTalkServer  # type: ignore


REQUIRED_FILES = [
    Path("/models/musetalkV15/musetalk.json"),
    Path("/models/musetalkV15/unet.pth"),
    Path("/models/dwpose/dw-ll_ucoco_384.pth"),
    Path("/models/face-parse-bisent/79999_iter.pth"),
    Path("/models/face-parse-bisent/resnet18-5c106cde.pth"),
    Path("/models/sd-vae/config.json"),
    Path("/models/sd-vae/diffusion_pytorch_model.bin"),
    Path("/models/syncnet/latentsync_syncnet.pt"),
    Path("/models/whisper/config.json"),
    Path("/models/whisper/pytorch_model.bin"),
    Path("/models/whisper/preprocessor_config.json"),
]


class InferRequest(BaseModel):
    job_id: str
    source_path: Path
    source_kind: str
    audio_path: Path
    options: dict[str, object] = Field(default_factory=dict)


app = FastAPI(title="MuseTalk Backend", version="0.1.0")
server = MuseTalkServer()
ready = False


def ensure_required_files() -> None:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing MuseTalk weights: {missing}")


@app.on_event("startup")
async def startup_event() -> None:
    global ready
    ensure_required_files()
    server.cache_dir = Path("/cache")
    server.landmarks_cache = server.cache_dir / "landmarks"
    server.latents_cache = server.cache_dir / "latents"
    server.whisper_cache = server.cache_dir / "whisper_features"
    for cache_dir in (server.cache_dir, server.landmarks_cache, server.latents_cache, server.whisper_cache):
        cache_dir.mkdir(parents=True, exist_ok=True)
    server.load_models(
        gpu_id=int(os.getenv("GPU_ID", "0")),
        unet_model_path="/models/musetalkV15/unet.pth",
        unet_config="/models/musetalkV15/musetalk.json",
        whisper_dir="/models/whisper",
        use_float16=os.getenv("USE_FLOAT16", "true").lower() == "true",
        version="v15",
    )
    ready = True


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, object]:
    if not ready or not server.is_loaded:
        raise HTTPException(status_code=503, detail="MuseTalk models are not loaded yet")
    return {
        "status": "ready",
        "device": str(server.device),
    }


@app.post("/infer")
async def infer(request: InferRequest) -> dict[str, str]:
    if request.source_kind not in {"image", "video"}:
        raise HTTPException(status_code=400, detail=f"Unsupported source kind: {request.source_kind}")
    if not request.source_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing source file: {request.source_path}")
    if not request.audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing audio file: {request.audio_path}")

    result_dir = Path("/results") / request.job_id
    result_dir.mkdir(parents=True, exist_ok=True)
    output_path = result_dir / "output.mp4"

    try:
        server.generate(
            video_path=str(request.source_path),
            audio_path=str(request.audio_path),
            output_path=str(output_path),
            fps=int(request.options.get("fps", os.getenv("MUSE_TALK_DEFAULT_FPS", "25"))),
            use_cache=bool(request.options.get("use_cache", os.getenv("MUSE_TALK_DEFAULT_USE_CACHE", "true").lower() == "true")),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "result_relative_path": str(output_path.relative_to(Path("/results"))),
        "result_filename": output_path.name,
    }
