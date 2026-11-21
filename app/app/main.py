import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from openai import OpenAI

app = FastAPI(title="DENYER DR Subtitle API", version="0.1.0")

MAX_VIDEO_BYTES = int(os.getenv("MAX_VIDEO_BYTES", str(200 * 1024 * 1024)))
MAX_AUDIO_CHUNK_SECONDS = int(os.getenv("MAX_AUDIO_CHUNK_SECONDS", "900"))
APP_ACCESS_TOKEN = os.getenv("APP_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def require_token(value: str | None) -> None:
    if not APP_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="Server token is not configured.")
    if value != APP_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized.")


def run_ffmpeg(args: list[str]) -> None:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
            capture_output=True, text=True, timeout=900
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="FFmpeg is not installed on the server.")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Audio preparation timed out.")
    if result.returncode != 0:
        raise HTTPException(status_code=422, detail="Could not extract audio from this video.")


def as_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {}


@app.get("/health")
def health():
    return {"ok": True, "service": "denyer-dr-subtitles"}


@app.post("/v1/transcribe")
async def transcribe_video(
    video: UploadFile = File(...),
    x_app_token: str | None = Header(default=None),
):
    require_token(x_app_token)
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Transcription service is not configured.")
    if not video.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    suffix = Path(video.filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".m4v", ".3gp", ".webm", ".mkv"}:
        suffix = ".mp4"

    with tempfile.TemporaryDirectory(prefix="denyerdr_") as temp:
        work = Path(temp)
        source = work / ("source" + suffix)
        size = 0
        try:
            with source.open("wb") as out:
                while True:
                    chunk = await video.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_VIDEO_BYTES:
                        raise HTTPException(status_code=413, detail="Video exceeds server upload limit.")
                    out.write(chunk)
        finally:
            await video.close()

        if size < 1024:
            raise HTTPException(status_code=400, detail="Video file is empty or too small.")

        audio = work / "audio.mp3"
        run_ffmpeg([
            "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
            "-b:a", "64k", "-f", "mp3", str(audio)
        ])

        chunks_dir = work / "chunks"
        chunks_dir.mkdir()
        pattern = str(chunks_dir / "part_%03d.mp3")
        run_ffmpeg([
            "-i", str(audio), "-f", "segment",
            "-segment_time", str(MAX_AUDIO_CHUNK_SECONDS),
            "-reset_timestamps", "1", "-c", "copy", pattern
        ])

        parts = sorted(chunks_dir.glob("part_*.mp3"))
        if not parts:
            raise HTTPException(status_code=422, detail="No audio track was found.")

        client = OpenAI(api_key=OPENAI_API_KEY)
        segments: list[dict] = []
        offset_seconds = 0.0

        try:
            for part in parts:
                with part.open("rb") as audio_file:
                    result = client.audio.transcriptions.create(
                        file=audio_file,
                        model="gpt-4o-transcribe-diarize",
                        response_format="diarized_json",
                        chunking_strategy="auto",
                    )
                data = as_dict(result)
                raw_segments = data.get("segments") or []
                for item in raw_segments:
                    item = as_dict(item)
                    text = str(item.get("text", "")).strip()
                    if not text:
                        continue
                    start = float(item.get("start", 0.0)) + offset_seconds
                    end = float(item.get("end", start)) + offset_seconds
                    segments.append({
                        "start": round(start, 3),
                        "end": round(max(start, end), 3),
                        "text": text,
                    })
                # Each part is made with a fixed-duration FFmpeg segment, except the last.
                offset_seconds += MAX_AUDIO_CHUNK_SECONDS
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Transcription provider failed. Check server logs.") from exc

        return {
            "language": "es",
            "segments": segments,
            "count": len(segments),
            "format": "denyer-dr-subtitles-v1",
        }
