from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


REQUIRED_FILES = [
    Path("/models/checkpoints/mapping_00109-model.pth.tar"),
    Path("/models/checkpoints/mapping_00229-model.pth.tar"),
    Path("/models/checkpoints/SadTalker_V0.0.2_256.safetensors"),
    Path("/models/checkpoints/SadTalker_V0.0.2_512.safetensors"),
    Path("/models/gfpgan/weights/alignment_WFLW_4HG.pth"),
    Path("/models/gfpgan/weights/detection_Resnet50_Final.pth"),
    Path("/models/gfpgan/weights/GFPGANv1.4.pth"),
    Path("/models/gfpgan/weights/parsing_parsenet.pth"),
]


class InferRequest(BaseModel):
    job_id: str
    source_path: Path
    source_kind: str
    audio_path: Path
    options: dict[str, object] = Field(default_factory=dict)


app = FastAPI(title="SadTalker Backend", version="0.1.0")
ready = False


def ensure_required_files() -> None:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing SadTalker weights: {missing}")


@app.on_event("startup")
async def startup_event() -> None:
    global ready
    ensure_required_files()
    ready = True


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    if not ready:
        raise HTTPException(status_code=503, detail="SadTalker weights are not ready")
    return {"status": "ready"}


@app.post("/infer")
async def infer(request: InferRequest) -> dict[str, str]:
    if request.source_kind != "image":
        raise HTTPException(status_code=400, detail="SadTalker only accepts image avatars")
    if not request.source_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing source file: {request.source_path}")
    if not request.audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing audio file: {request.audio_path}")

    result_dir = Path("/results") / request.job_id
    result_dir.mkdir(parents=True, exist_ok=True)

    size = int(request.options.get("size", os.getenv("SADTALKER_DEFAULT_SIZE", "256")))
    preprocess = str(request.options.get("preprocess", os.getenv("SADTALKER_DEFAULT_PREPROCESS", "crop")))
    enhancer = str(request.options.get("enhancer", os.getenv("SADTALKER_DEFAULT_ENHANCER", "gfpgan")))
    still = bool(request.options.get("still", os.getenv("SADTALKER_DEFAULT_STILL", "true").lower() == "true"))

    command = [
        "python",
        "/opt/SadTalker/inference.py",
        "--driven_audio",
        str(request.audio_path),
        "--source_image",
        str(request.source_path),
        "--result_dir",
        str(result_dir),
        "--preprocess",
        preprocess,
        "--enhancer",
        enhancer,
        "--size",
        str(size),
    ]
    if still:
        command.append("--still")

    result = subprocess.run(
        command,
        cwd="/opt/SadTalker",
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"SadTalker failed with exit code {result.returncode}: {result.stderr}",
        )

    candidates = sorted(result_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime)
    if not candidates:
        raise HTTPException(status_code=500, detail="SadTalker completed without producing an MP4")
    output_path = candidates[-1]
    return {
        "result_relative_path": str(output_path.relative_to(Path("/results"))),
        "result_filename": output_path.name,
    }
