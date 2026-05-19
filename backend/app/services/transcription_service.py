"""
City Brain — Speech Transcription Service
Uses faster-whisper (local, offline) to transcribe audio.
Model is loaded once and reused across requests.
"""

import logging
import tempfile
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-loaded — only downloaded/loaded on first transcription request
_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper 'base' model (first-time download ~145MB)...")
        # device="cpu", compute_type="int8" — works on any machine without a GPU
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _whisper_model


# Map app language codes → Whisper language codes
LANG_MAP = {"en": "en", "hi": "hi", "kn": "kn", "": None}


def transcribe_audio(audio_bytes: bytes, language: Optional[str] = None) -> str:
    """
    Transcribe raw audio bytes using local Whisper.
    language: "en" | "hi" | "kn" | None (auto-detect)
    Returns transcribed text string.
    """
    model = _get_model()
    whisper_lang = LANG_MAP.get(language or "", None)

    # Write to a temp file — faster-whisper needs a file path
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            language=whisper_lang,
            beam_size=5,
            vad_filter=True,          # skip silent segments
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info(f"Transcribed ({info.language}, {info.duration:.1f}s): {text[:80]}")
        return text
    finally:
        os.unlink(tmp_path)
