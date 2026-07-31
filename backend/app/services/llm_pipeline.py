"""
City Brain — LLM Complaint Processing Pipeline
Handles: Translation → LLM Parsing → Classification → Priority Scoring
Uses an open-source LLM by default. Fine-tuned model files can stay in the
project, but this runtime path does not require the trained model.
"""

import httpx
import json
import logging
import re
from typing import Optional
from app.core.config import settings
from app.core.department_catalog import (
    CATEGORY_TO_DEPARTMENT as CATALOG_CATEGORY_TO_DEPARTMENT,
    VALID_CATEGORIES as CATALOG_VALID_CATEGORIES,
    category_prompt_text,
    department_prompt_lines,
)
from app.schemas.schemas import ComplaintParsed, LLMParseResponse

logger = logging.getLogger(__name__)


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

# Runtime uses the shared 19-organization catalog. The inline block above is
# retained only as historical context for older demo data.
CATEGORY_TO_DEPARTMENT = CATALOG_CATEGORY_TO_DEPARTMENT
VALID_CATEGORIES = CATALOG_VALID_CATEGORIES

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
    "metro_service": 2,
    "metro_station": 2,
    "metro_access": 2,
    "layout_issue": 2,
    "land_use": 2,
    "development_work": 2,
    "solid_waste": 2,
    "waste_collection": 3,
    "air_pollution": 4,
    "water_pollution": 4,
    "industrial_pollution": 4,
    "fire_hazard": 5,
    "fire_emergency": 5,
    "building_safety": 4,
    "transmission_line": 5,
    "transformer": 5,
    "substation": 4,
    "state_road": 3,
    "public_building": 3,
    "bridge_damage": 4,
    "vehicle_violation": 2,
    "vehicle_pollution": 2,
    "transport_permit": 1,
    "footpath": 3,
    "cycle_track": 2,
    "pedestrian_access": 3,
    "public_safety": 3,
    "law_order": 3,
    "public_nuisance": 2,
    "public_health": 4,
    "mosquito_menace": 4,
    "sanitation": 3,
    "tree_cutting": 4,
    "urban_forest": 3,
    "wildlife_rescue": 4,
    "public_garden": 2,
    "landscaping": 1,
    "flooding_emergency": 5,
    "storm_damage": 5,
    "disaster_response": 5,
    "other": 2,
}

# Keywords that bump priority UP
URGENCY_KEYWORDS = {
    5: ["emergency", "danger", "life threatening", "flooding", "collapse", "fire", "electrocution", "burst", "sparks", "safety violation"],
    4: ["urgent", "severe", "broken main", "sewage overflow", "accident", "stuck", "children at risk", "pollution", "mosquito"],
    3: ["weeks", "months", "repeated", "no response", "multiple complaints"],
}


# ──────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are City Brain's complaint analysis engine for Bengaluru, India.

Your job: Parse a citizen's complaint message and extract structured complaint data.

IMPORTANT RULES:
1. A single message may contain MULTIPLE complaints. Extract each one separately.
2. Map each complaint to exactly ONE category from this list:
   {category_prompt_text()}

3. Map each complaint to the correct department:
{department_prompt_lines()}
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
{{
  "complaints": [
    {{
      "category": "category_name",
      "department": "DEPARTMENT_CODE",
      "description": "Clean, concise English description of the issue",
      "location_text": "Extracted location or null",
      "severity": 3,
      "confidence": 0.92
    }}
  ]
}}

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


LOCATION_PATTERN = re.compile(
    r"\b(?:in\s+front\s+of|front\s+of|opposite|outside|beside|behind|around|near|at|on|in)\s+(?:the\s+)?([a-z0-9 .'-]+?)(?=\s+(?:and|also|but|with|due to)\b|[,.]|$)",
    re.IGNORECASE,
)

TEXT_NORMALIZATION_REPLACEMENTS = [
    (r"\bstreet\s+lite\b|\bstreetlite\b|\bstreat\s*light\b|\bstreet\s+lamp\b", "streetlight"),
    (r"\bbrakage\b|\bbrekage\b|\bbreakge\b", "breakage"),
    (r"\bbrken\b|\bborken\b|\bbrokn\b", "broken"),
    (r"\bbloked\b|\bblokage\b|\bblockge\b", "blockage"),
    (r"\bleakge\b|\blekage\b|\bleakgae\b|\bleackage\b", "leakage"),
    (r"\bdamagae\b|\bdamagee\b|\bdamge\b|\bdamege\b|\bdamag\b", "damage"),
    (r"\bgarbge\b|\bgarbagee\b|\bgarbgae\b", "garbage"),
    (r"\bdrinage\b|\bdrainaige\b|\bdrange\b", "drainage"),
    (r"\bsewge\b|\bsewrage\b|\bsewr\b", "sewage"),
    (r"\bsingal\b|\bsignalz\b", "signal"),
    (r"\bfloyiver\b|\bflyvoer\b|\bfliyover\b|\bflyovr\b|\bflyoverr\b", "flyover"),
    (r"\bbaiyappanahlli\b|\bbaiyapanahalli\b|\bbyappanahalli\b|\bbayappanahalli\b", "baiyappanahalli"),
]


def normalize_complaint_text(text: str) -> str:
    """Clean common speech/typing mistakes before deterministic parsing."""
    normalized = text.lower()
    normalized = re.sub(r"[^a-z0-9\s.,'-]", " ", normalized)
    for pattern, replacement in TEXT_NORMALIZATION_REPLACEMENTS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


RULE_BASED_ISSUES = [
    {
        "category": "water_leakage",
        "department": "BWSSB",
        "severity": 4,
        "confidence": 0.92,
        "description": "Water pipe leakage or breakage",
        "patterns": [
            r"\bwater\s+pipe\s+(?:breakage|broken|burst|leak|leakage|leaking)\b",
            r"\bpipe\s+(?:breakage|broken|burst|leak|leakage|leaking)\b",
            r"\bwater\s+(?:leak|leakage|leaking|line\s+leak|pipeline\s+leak)\b",
            r"\b(?:leak|leakage|leaking)\s+(?:water|pipe|pipeline)\b",
        ],
    },
    {
        "category": "streetlight",
        "department": "BESCOM",
        "severity": 3,
        "confidence": 0.92,
        "description": "Streetlight is broken or not working",
        "patterns": [
            r"\bstreet\s*light\s+(?:broken|not working|not work|not working properly|off|failed|damaged|fused|issue|problem)\b",
            r"\bstreetlight\s+(?:broken|not working|not work|not working properly|off|failed|damaged|fused|issue|problem)\b",
            r"\bbroken\s+street\s*light\b",
            r"\b(?:broken|damaged|fused|off)\s+streetlight\b",
        ],
    },
    {
        "category": "drainage",
        "department": "BBMP",
        "severity": 4,
        "confidence": 0.9,
        "description": "Drainage blockage or rainwater flooding",
        "patterns": [
            r"\bdrain(?:age)?\s+(?:blocked|blockage|overflow|clogged|issue|problem)\b",
            r"\b(?:blocked|clogged|overflowing)\s+drain(?:age)?\b",
            r"\brain\s*water\s+(?:blocked|overflow|flooding|logging|stuck)\b",
            r"\bwater\s*logging\b",
            r"\broad\s+(?:blocked|blockage|flooded)\b.*\brain\b",
        ],
    },
    {
        "category": "pothole",
        "department": "BBMP",
        "severity": 3,
        "confidence": 0.9,
        "description": "Pothole on the road",
        "patterns": [r"\bpotholes?\b", r"\broad\s+hole\b", r"\bhole\s+in\s+(?:the\s+)?road\b"],
    },
    {
        "category": "road_damage",
        "department": "BBMP",
        "severity": 3,
        "confidence": 0.88,
        "description": "Road is damaged or blocked",
        "patterns": [
            r"\broad\s+(?:damaged|damage|broken|break|breakage|cracked|blocked|blockage|caved|collapsed|issue|problem)\b",
            r"\broad\s+(?:is|has been|was|got)\s+(?:damaged|damage|broken|cracked|blocked|caved|collapsed)\b",
            r"\b(?:damaged|broken|cracked|blocked|collapsed|bad)\s+road\b",
            r"\bblocked\s+road\b",
        ],
    },
    {
        "category": "garbage",
        "department": "BSWML",
        "severity": 2,
        "confidence": 0.9,
        "description": "Garbage or waste not cleared",
        "patterns": [
            r"\bgarbage\b",
            r"\btrash\b",
            r"\bwaste\b",
            r"\bgarbage\s+(?:pile|piled|overflow|not cleared|not collected|issue|problem)\b",
            r"\b(?:uncollected|overflowing)\s+(?:garbage|waste|trash)\b",
        ],
    },
    {
        "category": "water_supply",
        "department": "BWSSB",
        "severity": 3,
        "confidence": 0.88,
        "description": "Water supply issue",
        "patterns": [
            r"\bno\s+water\s+supply\b",
            r"\bwater\s+(?:is\s+)?(?:not coming|not available|stopped|pressure|shortage|supply\s+issue|supply\s+problem)\b",
            r"\blow\s+water\s+pressure\b",
        ],
    },
    {
        "category": "power_outage",
        "department": "BESCOM",
        "severity": 4,
        "confidence": 0.9,
        "description": "Power outage in the area",
        "patterns": [
            r"\bpower\s+(?:outage|cut|failure|not working)\b",
            r"\bno\s+power\b",
            r"\belectricity\s+(?:cut|outage|failure|not working|issue|problem)\b",
        ],
    },
    {
        "category": "traffic_signal",
        "department": "BTP",
        "severity": 3,
        "confidence": 0.88,
        "description": "Traffic signal issue",
        "patterns": [
            r"\btraffic\s+signal\s+(?:broken|not working|failed|issue|problem|wrong|stuck)\b",
            r"\bsignal\s+(?:broken|not working|failed|issue|problem|wrong|stuck)\b",
        ],
    },
    {
        "category": "traffic_congestion",
        "department": "BTP",
        "severity": 3,
        "confidence": 0.86,
        "description": "Traffic congestion or road safety issue",
        "patterns": [r"\btraffic\s+(?:jam|congestion|blocked|issue|problem)\b", r"\bheavy\s+traffic\b"],
    },
    {
        "category": "illegal_parking",
        "department": "BTP",
        "severity": 2,
        "confidence": 0.86,
        "description": "Illegal parking issue",
        "patterns": [r"\billegal\s+parking\b", r"\bwrong\s+parking\b", r"\bvehicle\s+parked\s+wrong\b"],
    },
    {
        "category": "public_transport",
        "department": "BMTC",
        "severity": 2,
        "confidence": 0.85,
        "description": "Public transport or bus stop issue",
        "patterns": [r"\bbus\s+stop\b", r"\bbmtc\b", r"\bbus\s+(?:not coming|shelter|route|late|issue|problem)\b"],
    },
    {
        "category": "metro_station",
        "department": "BMRCL",
        "severity": 2,
        "confidence": 0.86,
        "description": "Metro station facility issue",
        "patterns": [r"\bmetro\s+(?:issue|problem|station|access|service|not working)\b", r"\bnamma\s+metro\b"],
    },
    {
        "category": "sewage",
        "department": "BBMP",
        "severity": 4,
        "confidence": 0.9,
        "description": "Sewage overflow or sewer issue",
        "patterns": [
            r"\bsewage\s+(?:overflow|leak|leakage|flowing|blocked|issue|problem)\b",
            r"\bsewer\s+(?:overflow|blocked|issue|problem)\b",
            r"\bmanhole\s+(?:overflow|blocked|open|broken)\b",
        ],
    },
    {
        "category": "tree_fall",
        "department": "BBMP",
        "severity": 5,
        "confidence": 0.9,
        "description": "Tree or branch fallen and blocking access",
        "patterns": [
            r"\btree\s+(?:fallen|fall|blocked|blocking|down)\b",
            r"\bfallen\s+tree\b",
            r"\bbranch\s+(?:fallen|blocking|down)\b",
        ],
    },
    {
        "category": "illegal_construction",
        "department": "BBMP",
        "severity": 2,
        "confidence": 0.86,
        "description": "Illegal construction issue",
        "patterns": [r"\billegal\s+construction\b", r"\bunauthorized\s+construction\b", r"\bbuilding\s+violation\b"],
    },
    {
        "category": "encroachment",
        "department": "BBMP",
        "severity": 2,
        "confidence": 0.86,
        "description": "Public space encroachment issue",
        "patterns": [r"\bencroachment\b", r"\bfootpath\s+occupied\b", r"\broad\s+occupied\b"],
    },
    {
        "category": "park_maintenance",
        "department": "HORTICULTURE",
        "severity": 1,
        "confidence": 0.84,
        "description": "Park maintenance issue",
        "patterns": [r"\bpark\s+(?:maintenance|dirty|damaged|issue|problem)\b", r"\bplayground\s+(?:broken|dirty|issue|problem)\b"],
    },
    {
        "category": "stray_animals",
        "department": "BBMP",
        "severity": 2,
        "confidence": 0.84,
        "description": "Stray animal issue",
        "patterns": [r"\bstray\s+(?:dog|dogs|animal|animals)\b", r"\bdog\s+menace\b"],
    },
    {
        "category": "air_pollution",
        "department": "KSPCB",
        "severity": 4,
        "confidence": 0.88,
        "description": "Air pollution complaint",
        "patterns": [r"\bair\s+pollution\b", r"\bfactory\s+smoke\b", r"\bindustrial\s+smoke\b"],
    },
    {
        "category": "fire_hazard",
        "department": "KSFES",
        "severity": 5,
        "confidence": 0.9,
        "description": "Fire safety hazard",
        "patterns": [r"\bfire\s+(?:hazard|risk|safety|emergency)\b", r"\bcatch\s+fire\b"],
    },
    {
        "category": "transformer",
        "department": "KPTCL",
        "severity": 5,
        "confidence": 0.88,
        "description": "Transformer or transmission safety issue",
        "patterns": [r"\btransformer\b", r"\btransmission\s+line\b", r"\bsubstation\b"],
    },
    {
        "category": "cycle_track",
        "department": "DULT",
        "severity": 2,
        "confidence": 0.86,
        "description": "Cycle track or pedestrian mobility issue",
        "patterns": [r"\bcycle\s+track\b", r"\bcycle\s+lane\b", r"\bpedestrian\b"],
    },
    {
        "category": "mosquito_menace",
        "department": "BBMP_HEALTH",
        "severity": 4,
        "confidence": 0.88,
        "description": "Mosquito or public health issue",
        "patterns": [r"\bmosquito\b", r"\bstagnant\s+water\b", r"\bpublic\s+health\b"],
    },
    {
        "category": "storm_damage",
        "department": "KSDMA",
        "severity": 5,
        "confidence": 0.88,
        "description": "Storm or disaster response issue",
        "patterns": [r"\bstorm\s+damage\b", r"\bdisaster\b", r"\bflooding\s+emergency\b"],
    },
]


def extract_location(text: str) -> Optional[str]:
    matches = [m.group(1).strip(" .,-") for m in LOCATION_PATTERN.finditer(text)]
    cleaned_matches = []
    for match in matches:
        cleaned = re.sub(r"^(?:front\s+of|of|our\s+area|area)\s+", "", match).strip(" .,-")
        cleaned = re.sub(r"^(?:road|street|lane|main)\s+(?:at|near|in|on)\s+", "", cleaned).strip(" .,-")
        cleaned_matches.append(cleaned)
    matches = cleaned_matches
    matches = [m for m in matches if len(m) >= 3]
    if not matches:
        return None
    # The last location phrase is often the shared location for all issues.
    return matches[-1][:120]


def normalize_location_text(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    normalized = re.sub(r"\b(the|near|in|at|on|road|street|main)\b", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def rule_based_parse(text: str) -> list[dict]:
    text_lower = normalize_complaint_text(text)
    location_text = extract_location(text_lower)
    issues = []
    seen_categories = set()

    for rule in RULE_BASED_ISSUES:
        if rule["category"] in seen_categories:
            continue
        if any(re.search(pattern, text_lower, flags=re.IGNORECASE) for pattern in rule["patterns"]):
            seen_categories.add(rule["category"])
            issues.append({
                "category": rule["category"],
                "department": rule["department"],
                "description": rule["description"],
                "location_text": location_text,
                "severity": rule["severity"],
                "confidence": rule["confidence"],
            })

    return issues


def merge_parser_results(
    llm_complaints: list[ComplaintParsed],
    rule_complaints: list[ComplaintParsed],
) -> list[ComplaintParsed]:
    if not rule_complaints:
        return llm_complaints

    llm_is_generic = (
        not llm_complaints
        or all(c.category == "other" or c.confidence < 0.5 for c in llm_complaints)
    )
    if llm_is_generic:
        return rule_complaints

    merged = [c for c in llm_complaints if c.category != "other"]
    keys = {(c.category, normalize_location_text(c.location_text)) for c in merged}

    for complaint in rule_complaints:
        key = (complaint.category, normalize_location_text(complaint.location_text))
        if key not in keys:
            merged.append(complaint)
            keys.add(key)

    return merged or rule_complaints


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

    # Step 3: Validate and fix LLM output, then add deterministic civic parsing
    validated_complaints = validate_and_fix(llm_result)
    rule_complaints = validate_and_fix(rule_based_parse(processing_text))
    validated_complaints = merge_parser_results(validated_complaints, rule_complaints)

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
    """Call the configured open-source LLM endpoint."""
    try:
        prompt = SYSTEM_PROMPT + "\n\n" + FEW_SHOT_EXAMPLES + f"\n\nParse this complaint:\n\n{text}"

        async with httpx.AsyncClient(timeout=60) as http_client:
            response = await http_client.post(settings.OPEN_SOURCE_LLM_URL, json={
                "model": settings.OPEN_SOURCE_LLM_MODEL,
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
        logger.error(f"Open-source LLM call failed: {e}")
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
        "metro": "metro_station",
        "layout": "layout_issue",
        "solid waste": "solid_waste",
        "collection": "waste_collection",
        "pollution": "air_pollution",
        "smoke": "air_pollution",
        "fire": "fire_hazard",
        "transformer": "transformer",
        "transmission": "transmission_line",
        "bridge": "bridge_damage",
        "vehicle": "vehicle_violation",
        "parking": "illegal_parking",
        "footpath": "footpath",
        "cycle": "cycle_track",
        "pedestrian": "pedestrian_access",
        "safety": "public_safety",
        "mosquito": "mosquito_menace",
        "health": "public_health",
        "sanitation": "sanitation",
        "wildlife": "wildlife_rescue",
        "garden": "public_garden",
        "storm": "storm_damage",
        "disaster": "disaster_response",
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
