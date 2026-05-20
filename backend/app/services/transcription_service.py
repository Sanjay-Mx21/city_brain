"""
City Brain speech transcription service.
Uses faster-whisper locally to transcribe speech or translate it to English.
"""

import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        logger.info("Loading Whisper 'base' model (first-time download is about 145MB)...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _whisper_model


LANG_MAP = {"en": "en", "hi": "hi", "kn": "kn", "": None}


def transcribe_audio(
    audio_bytes: bytes,
    language: Optional[str] = None,
    translate_to_english: bool = True,
) -> dict:
    """
    Transcribe audio or translate speech to English.
    language can be "en", "hi", "kn", or None for auto-detect.
    """
    model = _get_model()
    whisper_lang = LANG_MAP.get(language or "", None)
    task = "translate" if translate_to_english else "transcribe"

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            language=whisper_lang,
            task=task,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info("Voice %s (%s, %.1fs): %s", task, info.language, info.duration, text[:80])
        return {
            "text": text,
            "english_text": text if translate_to_english else None,
            "detected_language": info.language,
            "duration": info.duration,
            "translated": translate_to_english,
        }
    finally:
        os.unlink(tmp_path)
