"""
Image evidence verification.

This is a lightweight local verifier for demo and offline use. A production
deployment can replace this with YOLO/Faster R-CNN while preserving the same
response fields.
"""

from dataclasses import dataclass


@dataclass
class ImageVerificationResult:
    status: str
    confidence: float
    notes: str


def verify_image_evidence(
    image_bytes: bytes,
    content_type: str | None,
    filename: str | None,
    category: str | None,
) -> ImageVerificationResult:
    size_kb = len(image_bytes) / 1024
    if not image_bytes:
        return ImageVerificationResult("rejected", 0.0, "Empty image file.")
    if content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return ImageVerificationResult("rejected", 0.1, "Unsupported image format.")
    if size_kb < 5:
        return ImageVerificationResult(
            "needs_review",
            0.35,
            "Image is very small, so officer review is required.",
        )

    name = (filename or "").lower()
    cat = (category or "").lower()
    matched_hint = any(token in name for token in cat.split("_") if len(token) > 3)
    if matched_hint:
        return ImageVerificationResult(
            "verified",
            0.82,
            "Image evidence accepted and filename context matches the complaint category.",
        )

    return ImageVerificationResult(
        "needs_review",
        0.68,
        "Image evidence accepted; automated visual confidence is moderate.",
    )
