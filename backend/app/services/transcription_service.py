"""
City Brain speech transcription service.
Uses faster-whisper locally to transcribe speech or translate it to English.
"""

import logging
import os
import tempfile
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_whisper_model = None
_whisper_model_name = None


def _get_model():
    global _whisper_model, _whisper_model_name
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        model_size = settings.WHISPER_MODEL_SIZE or "small"
        try:
            logger.info(
                "Loading Whisper '%s' model for multilingual voice translation...",
                model_size,
            )
            _whisper_model = WhisperModel(
                model_size,
                device=settings.WHISPER_DEVICE,
                compute_type=settings.WHISPER_COMPUTE_TYPE,
            )
            _whisper_model_name = model_size
        except Exception:
            if model_size == "base":
                raise
            logger.exception("Failed to load Whisper '%s'. Falling back to 'base'.", model_size)
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
            _whisper_model_name = "base"
        logger.info("Whisper model loaded.")
    return _whisper_model


LANG_MAP = {"en": "en", "hi": "hi", "kn": "kn", "": None}

CIVIC_TERMS = {
    "accident",
    "blocked",
    "blockage",
    "broken",
    "bus",
    "collapsed",
    "construction",
    "damage",
    "damaged",
    "dirty",
    "drain",
    "drainage",
    "electric",
    "electricity",
    "flood",
    "flooded",
    "footpath",
    "garbage",
    "clog",
    "clogged",
    "leak",
    "leakage",
    "leaking",
    "light",
    "manhole",
    "overflow",
    "pipe",
    "pothole",
    "rain",
    "rainwater",
    "road",
    "sewage",
    "sewer",
    "signal",
    "smell",
    "street",
    "traffic",
    "trash",
    "waste",
    "water",
    "waterlogged",
    "waterlogging",
}

HALLUCINATION_TERMS = {
    "bride",
    "married",
    "relationship",
    "affectionate",
    "emotional state",
    "girl",
    "hotel",
}


def _score_segments(segments_list) -> dict:
    if not segments_list:
        return {
            "text": "",
            "avg_logprob": None,
            "no_speech_probability": None,
            "compression_ratio": None,
            "duration": 0,
        }

    total_duration = 0.0
    weighted_logprob = 0.0
    no_speech_probs = []
    compression_ratios = []
    texts = []

    for segment in segments_list:
        duration = max((segment.end or 0) - (segment.start or 0), 0.01)
        total_duration += duration
        weighted_logprob += (segment.avg_logprob or -2.0) * duration
        no_speech_probs.append(segment.no_speech_prob or 0.0)
        compression_ratios.append(segment.compression_ratio or 0.0)
        if segment.text:
            texts.append(segment.text.strip())

    return {
        "text": " ".join(texts).strip(),
        "avg_logprob": weighted_logprob / total_duration if total_duration else None,
        "no_speech_probability": max(no_speech_probs) if no_speech_probs else None,
        "compression_ratio": max(compression_ratios) if compression_ratios else None,
        "duration": total_duration,
    }


def _translation_quality(text: str, metrics: dict, requested_language: Optional[str]) -> dict:
    normalized = f" {text.lower()} "
    warnings = []

    if not text.strip():
        warnings.append("No speech was detected.")

    avg_logprob = metrics.get("avg_logprob")
    if avg_logprob is not None and avg_logprob < -1.15:
        warnings.append("The speech model confidence is low.")

    no_speech_probability = metrics.get("no_speech_probability")
    if no_speech_probability is not None and no_speech_probability > 0.65:
        warnings.append("The recording may contain silence or background noise.")

    compression_ratio = metrics.get("compression_ratio")
    if compression_ratio is not None and compression_ratio > 2.6:
        warnings.append("The translation may be repetitive or unstable.")

    civic_match = any(f" {term} " in normalized for term in CIVIC_TERMS)
    suspicious_match = any(term in normalized for term in HALLUCINATION_TERMS)

    if requested_language in {"kn", "hi"} and text.strip() and not civic_match:
        warnings.append("The English translation does not look like a civic complaint.")
    if suspicious_match:
        warnings.append("The translation contains words that often indicate a hallucinated result.")

    review_required = bool(warnings)
    confidence = 0.9
    if avg_logprob is not None:
        confidence = max(0.05, min(0.95, (avg_logprob + 2.0) / 2.0))
    if not civic_match and requested_language in {"kn", "hi"}:
        confidence = min(confidence, 0.45)
    if suspicious_match:
        confidence = min(confidence, 0.25)
    if not text.strip():
        confidence = 0.0

    return {
        "confidence": round(confidence, 2),
        "review_required": review_required,
        "quality": "low" if review_required else "ok",
        "warnings": warnings,
    }


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
        segments_list = list(segments)
        metrics = _score_segments(segments_list)
        text = metrics["text"]
        quality = _translation_quality(text, metrics, language)
        logger.info(
            "Voice %s (%s, %.1fs, quality=%s, confidence=%.2f): %s",
            task,
            info.language,
            info.duration,
            quality["quality"],
            quality["confidence"],
            text[:80],
        )
        return {
            "text": text,
            "english_text": text if translate_to_english else None,
            "detected_language": info.language,
            "duration": info.duration,
            "translated": translate_to_english,
            "model": _whisper_model_name,
            "avg_logprob": metrics["avg_logprob"],
            "no_speech_probability": metrics["no_speech_probability"],
            "compression_ratio": metrics["compression_ratio"],
            **quality,
        }
    finally:
        os.unlink(tmp_path)
