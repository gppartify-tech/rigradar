"""Safe image uploads (marketplace photos and avatars).

Every upload is opened with Pillow: anything that is not a real image is rejected,
the picture is re-encoded (which strips EXIF data such as GPS location and any
payload hidden in the file) and resized so it never exceeds MAX_SIDE pixels.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings

MAX_SIDE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}


def upload_root() -> Path:
    root = Path(settings.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_image(upload: UploadFile, folder: str, max_side: int = MAX_SIDE) -> str:
    """Validate + store an uploaded image. Returns its public URL path (/uploads/...)."""
    limit = settings.max_upload_mb * 1024 * 1024
    raw = upload.file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"Image is larger than {settings.max_upload_mb} MB")
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()  # detects truncated / fake files
        image = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise HTTPException(400, "The file is not a valid image") from exc
    if image.format not in ALLOWED_FORMATS:
        raise HTTPException(400, "Only JPEG, PNG, WEBP or GIF images are allowed")

    image = ImageOps.exif_transpose(image)  # respect phone rotation, then drop EXIF
    image.thumbnail((max_side, max_side))
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")

    directory = upload_root() / folder
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.webp"
    image.save(directory / name, "WEBP", quality=85, method=4)
    return f"/uploads/{folder}/{name}"


def delete_upload(url: str | None) -> None:
    if not url or not url.startswith("/uploads/"):
        return
    path = (upload_root() / url.removeprefix("/uploads/")).resolve()
    if upload_root().resolve() in path.parents and path.exists():
        path.unlink()
