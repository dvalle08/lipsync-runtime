from tempfile import SpooledTemporaryFile

from PIL import Image

from talking_head_runtime.models import Engine
from talking_head_runtime.storage import JobStorage


def test_musetalk_odd_image_is_padded_to_even_dimensions(tmp_path) -> None:
    storage = JobStorage(tmp_path / "jobs")

    stored = storage.store_inputs(
        "job-odd",
        engine=Engine.MUSE_TALK,
        source_filename="avatar.png",
        source_file=_spooled_png((3, 5)),
        audio_filename="audio.wav",
        audio_file=_spooled_bytes(b"audio"),
    )

    assert stored.source_path.name == "source_musetalk.png"
    with Image.open(stored.source_path) as image:
        assert image.size == (4, 6)


def test_musetalk_even_image_is_left_unchanged(tmp_path) -> None:
    storage = JobStorage(tmp_path / "jobs")

    stored = storage.store_inputs(
        "job-even",
        engine=Engine.MUSE_TALK,
        source_filename="avatar.png",
        source_file=_spooled_png((4, 6)),
        audio_filename="audio.wav",
        audio_file=_spooled_bytes(b"audio"),
    )

    assert stored.source_path.name == "source.png"
    with Image.open(stored.source_path) as image:
        assert image.size == (4, 6)


def test_sadtalker_odd_image_is_left_unchanged(tmp_path) -> None:
    storage = JobStorage(tmp_path / "jobs")

    stored = storage.store_inputs(
        "job-sadtalker",
        engine=Engine.SADTALKER,
        source_filename="avatar.png",
        source_file=_spooled_png((3, 5)),
        audio_filename="audio.wav",
        audio_file=_spooled_bytes(b"audio"),
    )

    assert stored.source_path.name == "source.png"
    with Image.open(stored.source_path) as image:
        assert image.size == (3, 5)


def _spooled_png(size: tuple[int, int]) -> SpooledTemporaryFile[bytes]:
    handle: SpooledTemporaryFile[bytes] = SpooledTemporaryFile()
    Image.new("RGBA", size, (255, 0, 0, 255)).save(handle, format="PNG")
    handle.seek(0)
    return handle


def _spooled_bytes(payload: bytes) -> SpooledTemporaryFile[bytes]:
    handle: SpooledTemporaryFile[bytes] = SpooledTemporaryFile()
    handle.write(payload)
    handle.seek(0)
    return handle
