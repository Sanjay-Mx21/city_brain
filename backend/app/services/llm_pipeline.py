"""
City Brain — LLM Complaint Processing Pipeline
Handles: Translation → LLM Parsing → Classification → Priority Scoring
This is the brain of City Brain.
"""

import httpx
import json
import logging
from typing import Optional
from app.core.config import settings
from app.schemas.schemas import ComplaintParsed, LLMParseResponse

logger = logging.getLogger(__name__)


OLLAMA_URL = "http://localhost:11434/api/generate"

# ──────────────────────────────────────────────
# DEPARTMENT MAPPING (used in prompt + validation)
# ──────────────────────────────────────────────

DEPARTMENT_MAPPING = {
    "BBMP": {
        "full_name": "Bruhat Bengaluru Mahanagara Palike",
        "categories": [
            "road_damage", "pothole", "garbage", "drainage", "sewage",
            "tree_fall", "park_maintenance", "illegal_construction",
            "encroachment", "stray_animals", "noise_pollution"
        ],
    },
    "BESCOM": {
        "full_name": "Bangalore Electricity Supply Company",
        "categories": ["streetlight", "electricity", "power_outage"],
    },
    "BWSSB": {
        "full_name": "Bangalore Water Supply and Sewerage Board",
        "categories": ["water_supply", "water_leakage"],
    },
    "BTP": {
        "full_name": "Bengaluru Traffic Police",
        "categories": ["traffic_signal"],
    },
    "BMTC": {
        "full_name": "Bangalore Metropolitan Transport Corporation",
        "categories": ["public_transport"],
    },
}

# Reverse lookup: category → department
CATEGORY_TO_DEPARTMENT = {}
for dept, info in DEPARTMENT_MAPPING.items():
    for cat in info["categories"]:
        CATEGORY_TO_DEPARTMENT[cat] = dept

VALID_CATEGORIES = list(CATEGORY_TO_DEPARTMENT.keys()) + ["other"]

# ──────────────────────────────────────────────
# PRIORITY SCORING RULES
# ──────────────────────────────────────────────

PRIORITY_RULES = {
    # Category → base priority (1-5)
    "water_leakage": 4,
    "power_outage": 4,
    "sewage": 4,
    "tree_fall": 5,
    "drainage": 3,
    "road_damage": 3,
    "pothole": 3,
    "garbage": 2,
    "streetlight": 3,
    "water_supply": 3,
    "electricity": 3,
    "traffic_signal": 3,
    "illegal_construction": 2,
    "noise_pollution": 2,
    "public_transport": 2,
    "park_maintenance": 1,
    "stray_animals": 2,
    "encroachment": 2,
    "other": 2,
}

# Keywords that bump priority UP
URGENCY_KEYWORDS = {
    5: ["emergency", "danger", "life threatening", "flooding", "collapse", "fire", "electrocution", "burst"],
    4: ["urgent", "severe", "broken main", "sewage overflow", "accident", "stuck", "children at risk"],
    3: ["weeks", "months", "repeated", "no response", "multiple complaints"],
}


# ──────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are City Brain's complaint analysis engine for Bengaluru, India.

Your job: Parse a citizen's complaint message and extract structured complaint data.

IMPORTANT RULES:
1. A single message may contain MULTIPLE complaints. Extract each one separately.
2. Map each complaint to exactly ONE category from this list:
   road_damage, pothole, streetlight, water_supply, water_leakage, sewage, garbage, 
   drainage, electricity, power_outage, tree_fall, illegal_construction, noise_pollution, 
   public_transport, traffic_signal, park_maintenance, stray_animals, encroachment, other

3. Map each complaint to the correct department:
   - BBMP: road_damage, pothole, garbage, drainage, sewage, tree_fall, park_maintenance, illegal_construction, encroachment, stray_animals, noise_pollution
   - BESCOM: streetlight, electricity, power_outage
   - BWSSB: water_supply, water_leakage
   - BTP: traffic_signal
   - BMTC: public_transport
   - GENERAL: other (when no clear department match)

4. Extract location if mentioned (street name, area, landmark, ward).
5. Rate severity 1-5:
   1 = Minor inconvenience (park bench broken)
   2 = Moderate (garbage not collected)
   3 = Significant (road damage, broken streetlight)
   4 = Severe (water main burst, power outage in area)
   5 = Critical/Emergency (flooding, tree fallen on road, electrical danger)

6. Rate your confidence 0.0-1.0 for each complaint.

RESPOND ONLY WITH VALID JSON in this exact format:
{
  "complaints": [
    {
      "category": "category_name",
      "department": "DEPARTMENT_CODE",
      "description": "Clean, concise English description of the issue",
      "location_text": "Extracted location or null",
      "severity": 3,
      "confidence": 0.92
    }
  ]
}

Do NOT include any text outside the JSON. Do NOT use markdown code blocks."""


FEW_SHOT_EXAMPLES = """
Example 1:
Input: "Our road has been broken for 3 months and the streetlight is also not working near Jayanagar 4th Block"
Output: {"complaints": [{"category": "road_damage", "department": "BBMP", "description": "Road has been damaged for 3 months", "location_text": "Jayanagar 4th Block", "severity": 3, "confidence": 0.95}, {"category": "streetlight", "department": "BESCOM", "description": "Streetlight not working", "location_text": "Jayanagar 4th Block", "severity": 3, "confidence": 0.93}]}

Example 2:
Input: "Water is not coming since 2 days in our area Koramangala and there is also garbage piled up on 80 feet road"
Output: {"complaints": [{"category": "water_supply", "department": "BWSSB", "description": "No water supply for 2 days", "location_text": "Koramangala", "severity": 4, "confidence": 0.94}, {"category": "garbage", "department": "BBMP", "description": "Garbage piled up on road", "location_text": "80 feet road, Koramangala", "severity": 2, "confidence": 0.91}]}

Example 3:
Input: "Big tree fallen on road blocking traffic in Indiranagar, very dangerous"
Output: {"complaints": [{"category": "tree_fall", "department": "BBMP", "description": "Large tree fallen on road blocking traffic, dangerous situation", "location_text": "Indiranagar", "severity": 5, "confidence": 0.97}]}
"""


# ──────────────────────────────────────────────
# CORE PIPELINE FUNCTIONS
# ──────────────────────────────────────────────

async def parse_complaint(text: str, language: str = "en") -> LLMParseResponse:
    """
    Main pipeline entry point.
    Takes citizen's raw text → returns structured complaint data.
    """
    original_text = text
    translated_text = None
    detected_language = language

    # Step 1: Translate if not English
    if language and language != "en":
        translated_text = await translate_text(text, source_lang=language, target_lang="en")
        processing_text = translated_text or text
        detected_language = language
    else:
        # Auto-detect language
        detected_language = detect_language(text)
        if detected_language != "en":
            translated_text = await translate_text(text, source_lang=detected_language, target_lang="en")
            processing_text = translated_text or text
        else:
            processing_text = text

    # Step 2: LLM parsing
    llm_result = await call_llm(processing_text)

    # Step 3: Validate and fix LLM output
    validated_complaints = validate_and_fix(llm_result)

    # Step 4: Apply priority scoring rules
    for complaint in validated_complaints:
        complaint.severity = calculate_priority(complaint.category, processing_text)

    return LLMParseResponse(
        original_text=original_text,
        translated_text=translated_text,
        detected_language=detected_language,
        complaints=validated_complaints,
    )


async def call_llm(text: str) -> list[dict]:
    """Call local Mistral-7B via Ollama."""
    try:
        prompt = SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES + f"\n\nParse this complaint:\n\n{text}"

        async with httpx.AsyncClient(timeout=60) as http_client:
            response = await http_client.post(OLLAMA_URL, json={
                "model": "citybrain-mistral",
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.1}
            })
            response.raise_for_status()
            data = response.json()
            parsed = json.loads(data["response"])

            if "complaints" in parsed:
                return parsed["complaints"]
            return [parsed] if isinstance(parsed, dict) else []

    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        return [{
            "category": "other",
            "department": "GENERAL",
            "description": text[:500],
            "location_text": None,
            "severity": 2,
            "confidence": 0.3,
        }]


def validate_and_fix(raw_complaints: list[dict]) -> list[ComplaintParsed]:
    """
    Rule-based second-pass validator.
    Fixes invalid categories, departments, and severity values.
    """
    validated = []
    for raw in raw_complaints:
        category = raw.get("category", "other").lower().strip()
        department = raw.get("department", "GENERAL").upper().strip()

        # Fix invalid category
        if category not in VALID_CATEGORIES:
            category = find_closest_category(category)

        # Fix department based on category (override LLM if wrong)
        correct_dept = CATEGORY_TO_DEPARTMENT.get(category, "GENERAL")
        if department != correct_dept and category != "other":
            logger.info(f"Overriding department: LLM said {department}, rule says {correct_dept} for {category}")
            department = correct_dept

        # Clamp severity
        severity = max(1, min(5, int(raw.get("severity", 2))))

        # Clamp confidence
        confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))

        validated.append(ComplaintParsed(
            category=category,
            department=department,
            description=raw.get("description", "No description provided"),
            location_text=raw.get("location_text"),
            severity=severity,
            confidence=confidence,
        ))

    return validated


def find_closest_category(category: str) -> str:
    """Simple keyword matching for misclassified categories."""
    keyword_map = {
        "road": "road_damage",
        "pothole": "pothole",
        "street light": "streetlight",
        "light": "streetlight",
        "water": "water_supply",
        "leak": "water_leakage",
        "pipe": "water_leakage",
        "sewer": "sewage",
        "garbage": "garbage",
        "trash": "garbage",
        "waste": "garbage",
        "drain": "drainage",
        "electric": "electricity",
        "power": "power_outage",
        "tree": "tree_fall",
        "traffic": "traffic_signal",
        "bus": "public_transport",
        "park": "park_maintenance",
        "dog": "stray_animals",
        "animal": "stray_animals",
        "construction": "illegal_construction",
        "noise": "noise_pollution",
        "encroach": "encroachment",
    }
    for keyword, cat in keyword_map.items():
        if keyword in category.lower():
            return cat
    return "other"


def calculate_priority(category: str, text: str) -> int:
    """
    Rule-based priority scoring.
    Base priority from category + keyword boosting.
    """
    base = PRIORITY_RULES.get(category, 2)
    text_lower = text.lower()

    # Check urgency keywords (highest match wins)
    for priority_level in [5, 4, 3]:
        for keyword in URGENCY_KEYWORDS.get(priority_level, []):
            if keyword in text_lower:
                return max(base, priority_level)

    return base


def detect_language(text: str) -> str:
    """
    Simple language detection based on Unicode ranges.
    For production, use Bhashini's language detection.
    """
    kannada_range = range(0x0C80, 0x0CFF + 1)
    devanagari_range = range(0x0900, 0x097F + 1)

    kannada_count = sum(1 for ch in text if ord(ch) in kannada_range)
    hindi_count = sum(1 for ch in text if ord(ch) in devanagari_range)
    total = len(text)

    if total == 0:
        return "en"
    if kannada_count / total > 0.3:
        return "kn"
    if hindi_count / total > 0.3:
        return "hi"
    return "en"


async def translate_text(
    text: str, source_lang: str, target_lang: str = "en"
) -> Optional[str]:
    """
    Translate text using Bhashini API.
    Falls back to returning original text if translation fails.
    """
    # If Bhashini keys not configured, return original
    if not settings.BHASHINI_API_KEY:
        logger.warning("Bhashini API key not configured. Skipping translation.")
        return text

    try:
        # Bhashini language codes
        lang_codes = {"en": "en", "kn": "kn", "hi": "hi"}

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": lang_codes.get(source_lang, source_lang),
                            "targetLanguage": lang_codes.get(target_lang, target_lang),
                        }
                    },
                }
            ],
            "inputData": {
                "input": [{"source": text}]
            },
        }

        headers = {
            "Authorization": settings.BHASHINI_API_KEY,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as http_client:
            response = await http_client.post(
                settings.BHASHINI_PIPELINE_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # Extract translated text from Bhashini response
            translated = (
                data.get("pipelineResponse", [{}])[0]
                .get("output", [{}])[0]
                .get("target", text)
            )
            return translated

    except Exception as e:
        logger.error(f"Bhashini translation failed: {e}")
        return text  # Return original on failure
