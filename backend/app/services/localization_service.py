"""
Small localization layer for citizen-facing messages.
External Bhashini translation can still be used for free-form complaint text;
these templates keep critical workflow messages predictable in demos.
"""

SUPPORTED_LANGUAGES = {"en", "hi", "kn"}

MESSAGES = {
    "complaint_created": {
        "en": "Your complaint has been registered successfully. Ticket IDs: {tickets}.",
        "hi": "आपकी शिकायत सफलतापूर्वक दर्ज हो गई है। टिकट आईडी: {tickets}।",
        "kn": "ನಿಮ್ಮ ದೂರು ಯಶಸ್ವಿಯಾಗಿ ದಾಖಲಾಗಿದೆ. ಟಿಕೆಟ್ ಐಡಿ: {tickets}.",
    },
    "status_pending": {
        "en": "Pending",
        "hi": "लंबित",
        "kn": "ಬಾಕಿ",
    },
    "status_assigned": {
        "en": "Assigned",
        "hi": "अधिकारी को सौंपा गया",
        "kn": "ಅಧಿಕಾರಿಗೆ ನೀಡಲಾಗಿದೆ",
    },
    "status_in_progress": {
        "en": "In progress",
        "hi": "कार्य जारी है",
        "kn": "ಕೆಲಸ ನಡೆಯುತ್ತಿದೆ",
    },
    "status_resolved": {
        "en": "Resolved",
        "hi": "समाधान हो गया",
        "kn": "ಪರಿಹರಿಸಲಾಗಿದೆ",
    },
    "status_escalated": {
        "en": "Escalated",
        "hi": "वरिष्ठ अधिकारी को भेजा गया",
        "kn": "ಹಿರಿಯ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ",
    },
    "status_closed": {
        "en": "Closed",
        "hi": "बंद",
        "kn": "ಮುಚ್ಚಲಾಗಿದೆ",
    },
}


def normalize_language(language: str | None) -> str:
    return language if language in SUPPORTED_LANGUAGES else "en"


def localize(key: str, language: str | None = "en", **values) -> str:
    lang = normalize_language(language)
    template = MESSAGES.get(key, MESSAGES.get(key, {})).get(lang)
    if not template:
        template = MESSAGES.get(key, {}).get("en", key)
    return template.format(**values)


def localized_status(status: str, language: str | None = "en") -> str:
    return localize(f"status_{status}", language)
