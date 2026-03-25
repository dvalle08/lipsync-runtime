from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


class Engine(StrEnum):
    MUSE_TALK = "musetalk"
    SADTALKER = "sadtalker"


class JobState(StrEnum):
    QUEUED = "queued"
    STARTING_BACKEND = "starting_backend"
    WARMING_MODEL = "warming_model"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StoredInputs(BaseModel):
    source_path: Path
    source_filename: str
    source_kind: str
    audio_path: Path
    audio_filename: str


class JobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid4().hex)
    engine: Engine
    state: JobState = JobState.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_source_path: Path
    input_source_filename: str
    input_source_kind: str
    input_audio_path: Path
    input_audio_filename: str
    options: dict[str, Any] = Field(default_factory=dict)
    result_relative_path: str | None = None
    result_filename: str | None = None
    attempts: int = 0
    error: str | None = None

    def mark(self, state: JobState, *, error: str | None = None) -> "JobRecord":
        return self.model_copy(
            update={
                "state": state,
                "updated_at": datetime.now(UTC),
                "error": error,
            }
        )


class CreateJobResponse(BaseModel):
    job_id: str
    state: JobState
    queue_depth: int


class JobStatusResponse(BaseModel):
    job_id: str
    engine: Engine
    state: JobState
    created_at: datetime
    updated_at: datetime
    attempts: int
    error: str | None
    result_filename: str | None
    result_url: str | None


class BackendInferenceRequest(BaseModel):
    job_id: str
    source_path: Path
    source_kind: str
    audio_path: Path
    options: dict[str, Any] = Field(default_factory=dict)


class BackendInferenceResponse(BaseModel):
    result_relative_path: str
    result_filename: str


class BackendStatus(BaseModel):
    active_engine: Engine | None = None
    last_used_at: datetime | None = None
    queue_depth: int = 0


def source_kind_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    raise ValueError(f"Unsupported source file extension: {path.suffix}")
