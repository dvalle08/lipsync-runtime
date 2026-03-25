from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import gdown
from huggingface_hub import hf_hub_download


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_checksum(path: Path, expected: str | None) -> None:
    if not expected:
        return
    actual = sha256sum(path)
    if actual != expected:
        raise RuntimeError(f"Checksum mismatch for {path}: expected {expected}, got {actual}")


def download_item(root: Path, item: dict[str, str]) -> None:
    target = root / item["destination"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        ensure_checksum(target, item.get("sha256"))
        print(f"skip {target}")
        return

    kind = item["kind"]
    if kind == "huggingface":
        downloaded = Path(
            hf_hub_download(
                repo_id=item["repo_id"],
                filename=item["filename"],
            )
        )
        shutil.copy2(downloaded, target)
    elif kind == "url":
        urllib.request.urlretrieve(item["url"], target)
    elif kind == "gdrive":
        gdown.download(id=item["file_id"], output=str(target), quiet=False)
    else:
        raise RuntimeError(f"Unsupported manifest kind: {kind}")

    if item.get("extract") == "zip":
        with zipfile.ZipFile(target) as archive:
            archive.extractall(target.parent)
    ensure_checksum(target, item.get("sha256"))
    print(f"downloaded {target}")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: download_weights.py <manifest.json> <destination_root>")
        return 1
    manifest_path = Path(sys.argv[1])
    destination_root = Path(sys.argv[2])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination_root.mkdir(parents=True, exist_ok=True)
    for item in manifest:
        download_item(destination_root, item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
