from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import SpooledTemporaryFile

from PIL import Image

from .models import Engine, StoredInputs, source_kind_for_path


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
        engine: Engine,
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

        stored_inputs = StoredInputs(
            source_path=source_path,
            source_filename=source_filename,
            source_kind=source_kind_for_path(source_path),
            audio_path=audio_path,
            audio_filename=audio_filename,
        )
        return self._normalize_stored_inputs(engine=engine, stored_inputs=stored_inputs)

    def _normalize_stored_inputs(self, *, engine: Engine, stored_inputs: StoredInputs) -> StoredInputs:
        if engine != Engine.MUSE_TALK or stored_inputs.source_kind != "image":
            return stored_inputs

        normalized_path = self._pad_image_to_even_dimensions(stored_inputs.source_path)
        if normalized_path == stored_inputs.source_path:
            return stored_inputs

        return stored_inputs.model_copy(update={"source_path": normalized_path})

    def _pad_image_to_even_dimensions(self, source_path: Path) -> Path:
        with Image.open(source_path) as image:
            width, height = image.size
            padded_width = width + (width % 2)
            padded_height = height + (height % 2)
            if (padded_width, padded_height) == (width, height):
                return source_path

            normalized_path = source_path.with_name(f"{source_path.stem}_musetalk{source_path.suffix}")
            padded = Image.new(image.mode, (padded_width, padded_height))
            padded.paste(image, (0, 0))

            # Duplicate the outer edge instead of adding a visible border.
            if padded_width != width:
                right_edge = image.crop((width - 1, 0, width, height))
                padded.paste(right_edge, (width, 0))
            if padded_height != height:
                bottom_edge = padded.crop((0, height - 1, padded_width, height))
                padded.paste(bottom_edge, (0, height))

            save_kwargs: dict[str, bytes | str] = {}
            if image.format:
                save_kwargs["format"] = image.format
            if exif := image.info.get("exif"):
                save_kwargs["exif"] = exif
            if icc_profile := image.info.get("icc_profile"):
                save_kwargs["icc_profile"] = icc_profile

            padded.save(normalized_path, **save_kwargs)
            return normalized_path
