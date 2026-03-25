from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .config import RuntimeSettings
from .docker_control import BackendManager, ComposeController
from .models import CreateJobResponse, Engine, JobRecord, JobState, JobStatusResponse, source_kind_for_path
from .queue import RedisJobStore
from .storage import JobStorage
from .worker import JobWorker, result_root_for_engine


def create_app() -> FastAPI:
    settings = RuntimeSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = RedisJobStore(settings)
        await store.connect()
        storage = JobStorage(settings.JOBS_ROOT)
        controller = ComposeController(settings)
        backend_manager = BackendManager(settings, controller)
        worker = JobWorker(settings=settings, store=store, backend_manager=backend_manager)
        await worker.start()

        app.state.settings = settings
        app.state.store = store
        app.state.storage = storage
        app.state.backend_manager = backend_manager
        app.state.worker = worker
        yield
        await worker.stop()
        await store.close()

    app = FastAPI(title="Talking Head Runtime", version="0.1.0", lifespan=lifespan)

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str]:
        try:
            await app.state.store.client.ping()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"status": "ready"}

    @app.get("/backends/status")
    async def backends_status() -> dict[str, Any]:
        queue_depth = await app.state.store.queue_depth()
        return app.state.backend_manager.snapshot(queue_depth).model_dump(mode="json")

    @app.post("/jobs/musetalk", response_model=CreateJobResponse, status_code=202)
    async def create_musetalk_job(
        source: UploadFile = File(...),
        audio: UploadFile = File(...),
        options_json: str = Form("{}"),
    ) -> CreateJobResponse:
        return await _create_job(app, Engine.MUSE_TALK, source, audio, options_json)

    @app.post("/jobs/sadtalker", response_model=CreateJobResponse, status_code=202)
    async def create_sadtalker_job(
        source: UploadFile = File(...),
        audio: UploadFile = File(...),
        options_json: str = Form("{}"),
    ) -> CreateJobResponse:
        return await _create_job(app, Engine.SADTALKER, source, audio, options_json)

    @app.get("/jobs/{job_id}", response_model=JobStatusResponse)
    async def get_job(job_id: str) -> JobStatusResponse:
        record = await app.state.store.load_job(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
        return _job_status_response(record)

    @app.get("/jobs/{job_id}/result")
    async def get_job_result(job_id: str) -> FileResponse:
        record = await app.state.store.load_job(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
        if record.state != JobState.SUCCEEDED or not record.result_relative_path:
            raise HTTPException(status_code=409, detail=f"Job is not ready: {record.state}")

        result_root = result_root_for_engine(app.state.settings, record.engine)
        result_path = result_root / record.result_relative_path
        if not result_path.exists():
            raise HTTPException(status_code=404, detail=f"Missing result artifact: {result_path}")
        return FileResponse(result_path, media_type="video/mp4", filename=record.result_filename)

    return app


app = create_app()


async def _create_job(
    app: FastAPI,
    engine: Engine,
    source: UploadFile,
    audio: UploadFile,
    options_json: str,
) -> CreateJobResponse:
    try:
        options = json.loads(options_json) if options_json else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid options_json: {exc}") from exc

    source_name = source.filename or "source.bin"
    audio_name = audio.filename or "audio.bin"
    source_kind_for_path(Path(source_name))

    draft = JobRecord(
        engine=engine,
        input_source_path=Path("/pending/source"),
        input_source_filename=source_name,
        input_source_kind="pending",
        input_audio_path=Path("/pending/audio"),
        input_audio_filename=audio_name,
        options=options,
    )
    stored_inputs = app.state.storage.store_inputs(
        draft.job_id,
        source_filename=source_name,
        source_file=source.file,
        audio_filename=audio_name,
        audio_file=audio.file,
    )
    job = draft.model_copy(
        update={
            "input_source_path": stored_inputs.source_path,
            "input_source_filename": stored_inputs.source_filename,
            "input_source_kind": stored_inputs.source_kind,
            "input_audio_path": stored_inputs.audio_path,
            "input_audio_filename": stored_inputs.audio_filename,
        }
    )
    queue_depth = await app.state.store.enqueue(job)
    return CreateJobResponse(job_id=job.job_id, state=job.state, queue_depth=queue_depth)


def _job_status_response(record: JobRecord) -> JobStatusResponse:
    result_url = None
    if record.state == JobState.SUCCEEDED:
        result_url = f"/jobs/{record.job_id}/result"
    return JobStatusResponse(
        job_id=record.job_id,
        engine=record.engine,
        state=record.state,
        created_at=record.created_at,
        updated_at=record.updated_at,
        attempts=record.attempts,
        error=record.error,
        result_filename=record.result_filename,
        result_url=result_url,
    )
