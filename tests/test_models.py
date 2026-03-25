from pathlib import Path

from talking_head_runtime.models import source_kind_for_path


def test_detects_image_source_kind() -> None:
    assert source_kind_for_path(Path("avatar.png")) == "image"


def test_detects_video_source_kind() -> None:
    assert source_kind_for_path(Path("avatar.mp4")) == "video"
