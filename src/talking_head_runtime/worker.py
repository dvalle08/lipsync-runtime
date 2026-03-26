from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path

import httpx

from .config import RuntimeSettings
from .docker_control import BackendManager
from .models import BackendInferenceRequest, Engine, JobRecord, JobState
from .queue import RedisJobStore


class JobWorker:
    def __init__(
        self,
        *,
        settings: RuntimeSettings,
        store: RedisJobStore,
        backend_manager: BackendManager,
    ) -> None:
        self.settings = settings
        self.store = store
        self.backend_manager = backend_manager
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.store.recover_processing_jobs()
        await self.backend_manager.reset()
        self._task = asyncio.create_task(self._run_forever(), name="job-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run_forever(self) -> None:
        while True:
            job_id = await self.store.pop_next_job()
            if job_id is None:
                await self.backend_manager.maybe_stop_idle_backend()
                continue
            job = await self.store.load_job(job_id)
            if job is None:
                await self.store.ack(job_id)
                continue
            should_ack = True
            try:
                await self._process(job)
            except asyncio.CancelledError:
                should_ack = False
                current = await self.store.load_job(job_id) or job
                await self.store.save_job(current.mark(JobState.QUEUED))
                await self.store.requeue_processing_job(job_id)
                raise
            except Exception as exc:  # noqa: BLE001
                failed = job.mark(JobState.FAILED, error=str(exc))
                failed = failed.model_copy(update={"attempts": job.attempts + 1})
                await self.store.save_job(failed)
            finally:
                if should_ack:
                    await self.store.ack(job_id)

    async def _process(self, job: JobRecord) -> None:
        starting = job.mark(JobState.STARTING_BACKEND)
        await self.store.save_job(starting)
        spec = await self.backend_manager.ensure_backend(job.engine)

        warming = starting.mark(JobState.WARMING_MODEL)
        await self.store.save_job(warming)

        request_payload = BackendInferenceRequest(
            job_id=job.job_id,
            source_path=job.input_source_path,
            source_kind=job.input_source_kind,
            audio_path=job.input_audio_path,
            options=job.options,
        )

        running = warming.mark(JobState.RUNNING)
        await self.store.save_job(running)

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{spec.base_url}/infer",
                json=request_payload.model_dump(mode="json"),
            )
        if not response.is_success:
            raise RuntimeError(f"{job.engine} inference failed: {response.status_code} {response.text}")

        payload = response.json()
        result_relative_path = payload["result_relative_path"]
        result_filename = payload["result_filename"]
        completed = running.mark(JobState.SUCCEEDED)
        completed = completed.model_copy(
            update={
                "result_relative_path": result_relative_path,
                "result_filename": result_filename,
            }
        )
        await self.store.save_job(completed)
        self.backend_manager.last_used_at = completed.updated_at


def result_root_for_engine(settings: RuntimeSettings, engine: Engine) -> Path:
    if engine == Engine.MUSE_TALK:
        return settings.MUSE_TALK_RESULTS_ROOT
    return settings.SADTALKER_RESULTS_ROOT
