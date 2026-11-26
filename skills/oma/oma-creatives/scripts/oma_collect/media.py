"""Media storage: images become ≤1600px JPEG at ~80% quality, videos 720p H.264 (skill Storage Rules)."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from PIL import Image, UnidentifiedImageError

_IMAGE_EDGE = 1600
_RAW_VIDEO_LIMIT = 80 * 1024 * 1024


def store_image(raw: Path, dest: Path) -> Path | None:
    """Decode, downscale and re-encode; a file that does not decode as an image is dropped."""
    try:
        with Image.open(raw) as image:
            image.load()
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.thumbnail((_IMAGE_EDGE, _IMAGE_EDGE))
            dest.parent.mkdir(parents=True, exist_ok=True)
            image.save(dest, format="JPEG", quality=80, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None
    finally:
        if raw != dest:
            raw.unlink(missing_ok=True)
    return dest


def store_video(raw: Path, dest: Path) -> Path | None:
    """Transcode to 720p H.264 with audio; without ffmpeg keep a raw file up to the size limit."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        dest.parent.mkdir(parents=True, exist_ok=True)
        command = [ffmpeg, "-y", "-loglevel", "error", "-i", str(raw), "-vf", "scale=-2:'min(720,ih)'",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-movflags", "+faststart",
                   str(dest)]
        done = subprocess.run(command, capture_output=True, timeout=600, check=False)
        if done.returncode == 0 and dest.is_file() and dest.stat().st_size:
            raw.unlink(missing_ok=True)
            return dest
    if raw.stat().st_size <= _RAW_VIDEO_LIMIT:
        raw.replace(dest)
        return dest
    raw.unlink(missing_ok=True)
    return None


def save(fetcher, url: str, folder: Path, stem: str, kind: str, *, referer: str | None = None) -> tuple[Path | None, str | None]:
    """Download one image or video into ``folder``; returns (stored path, failure reason)."""
    raw, info = fetcher.download(url, folder / f".{stem}.part", referer=referer)
    if raw is None:
        return None, info
    if kind == "video" or (info or "").startswith("video/"):
        stored = store_video(raw, folder / f"{stem}.mp4")
        return stored, None if stored else "video too large to keep without ffmpeg"
    stored = store_image(raw, folder / f"{stem}.jpg")
    return stored, None if stored else f"not a decodable image ({info})"
