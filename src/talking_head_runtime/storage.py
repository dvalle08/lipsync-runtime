from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import SpooledTemporaryFile

from .models import StoredInputs, source_kind_for_path


@dataclass(slots=True)
class JobWorkspace:
    job_dir: Path
    inputs_dir: Path
    metadata_dir: Path


class JobStorage:
    def __init__(self, jobs_root: Path) -> None:
        self.jobs_root = jobs_root
        self.jobs_root.mkdir(parents=True, exist_ok=True)

    def workspace_for(self, job_id: str) -> JobWorkspace:
        job_dir = self.jobs_root / job_id
        inputs_dir = job_dir / "inputs"
        metadata_dir = job_dir / "metadata"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        return JobWorkspace(job_dir=job_dir, inputs_dir=inputs_dir, metadata_dir=metadata_dir)

    def store_inputs(
        self,
        job_id: str,
        *,
        source_filename: str,
        source_file: SpooledTemporaryFile[bytes],
        audio_filename: str,
        audio_file: SpooledTemporaryFile[bytes],
    ) -> StoredInputs:
        workspace = self.workspace_for(job_id)
        source_suffix = Path(source_filename).suffix or ".bin"
        audio_suffix = Path(audio_filename).suffix or ".bin"

        source_path = workspace.inputs_dir / f"source{source_suffix}"
        audio_path = workspace.inputs_dir / f"audio{audio_suffix}"

        source_file.seek(0)
        audio_file.seek(0)
        with source_path.open("wb") as source_handle:
            shutil.copyfileobj(source_file, source_handle)
        with audio_path.open("wb") as audio_handle:
            shutil.copyfileobj(audio_file, audio_handle)

        return StoredInputs(
            source_path=source_path,
            source_filename=source_filename,
            source_kind=source_kind_for_path(source_path),
            audio_path=audio_path,
            audio_filename=audio_filename,
        )
