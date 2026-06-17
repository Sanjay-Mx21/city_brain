"""
City Brain Model Kit - LLM Complaint Processing Pipeline

This standalone file is the trained-model inference pipeline packaged with the
City Brain model kit. It mirrors the backend service contract:

    raw citizen text -> multi-issue extraction -> department routing
    -> severity scoring -> JSON response

The live backend can use the same logic by wiring `parse_complaint()` or
`classify_complaint()` into its service layer. The file is intentionally
self-contained so it can run inside a demo folder, Colab export, or Ollama
model kit without importing the web backend.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Optional

import httpx


logger = logging.getLogger("citybrain.model_kit.llm_pipeline")


# ---------------------------------------------------------------------------
# Model Runtime Configuration
# ---------------------------------------------------------------------------

OLLAMA_GENERATE_URL = os.getenv("CITYBRAIN_OLLAMA_URL", "http://localhost:11434/api/generate")
TRAINED_MODEL_NAME = os.getenv("CITYBRAIN_MODEL_NAME", "citybrain")
FALLBACK_MODEL_NAME = os.getenv("CITYBRAIN_FALLBACK_MODEL", "phi3.5")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("CITYBRAIN_LLM_TIMEOUT", "60"))


# ---------------------------------------------------------------------------
# Civic Department Catalog
# ---------------------------------------------------------------------------

DEPARTMENT_CATALOG = [
    {
        "name": "BBMP",
        "full_name": "Bruhat Bengaluru Mahanagara Palike",
        "categories": [
            "road_damage",
            "pothole",
            "drainage",
            "sewage",
            "tree_fall",
            "illegal_construction",
            "encroachment",
            "stray_animals",
            "noise_pollution",
        ],
    },
    {
        "name": "BESCOM",
        "full_name": "Bangalore Electricity Supply Company",
        "categories": ["streetlight", "electricity", "power_outage"],
    },
    {
        "name": "BWSSB",
        "full_name": "Bangalore Water Supply and Sewerage Board",
        "categories": ["water_supply", "water_leakage"],
    },
    {
        "name": "BTP",
        "full_name": "Bengaluru Traffic Police",
        "categories": ["traffic_signal", "traffic_congestion", "illegal_parking"],
    },
    {
        "name": "BMTC",
        "full_name": "Bangalore Metropolitan Transport Corporation",
        "categories": ["public_transport", "bus_stop", "bus_service"],
    },
    {
        "name": "BMRCL",
        "full_name": "Bangalore Metro Rail Corporation Limited",
        "categories": ["metro_service", "metro_station", "metro_access"],
    },
    {
        "name": "BDA",
        "full_name": "Bangalore Development Authority",
        "categories": ["layout_issue", "land_use", "development_work"],
    },
    {
        "name": "BSWML",
        "full_name": "Bengaluru Solid Waste Management Limited",
        "categories": ["garbage", "solid_waste", "waste_collection"],
    },
    {
        "name": "KSPCB",
        "full_name": "Karnataka State Pollution Control Board",
        "categories": ["air_pollution", "water_pollution", "industrial_pollution"],
    },
    {
        "name": "KSFES",
        "full_name": "Karnataka State Fire and Emergency Services",
        "categories": ["fire_hazard", "fire_emergency", "building_safety"],
    },
    {
        "name": "KPTCL",
        "full_name": "Karnataka Power Transmission Corporation Limited",
        "categories": ["transmission_line", "transformer", "substation"],
    },
    {
        "name": "PWD",
        "full_name": "Public Works Department, Karnataka",
        "categories": ["state_road", "public_building", "bridge_damage"],
    },
    {
        "name": "RTO",
        "full_name": "Regional Transport Office Bengaluru",
        "categories": ["vehicle_violation", "vehicle_pollution", "transport_permit"],
    },
    {
        "name": "DULT",
        "full_name": "Directorate of Urban Land Transport",
        "categories": ["footpath", "cycle_track", "pedestrian_access"],
    },
    {
        "name": "KSP",
        "full_name": "Bengaluru City Police",
        "categories": ["public_safety", "law_order", "public_nuisance"],
    },
    {
        "name": "BBMP_HEALTH",
        "full_name": "BBMP Health Department",
        "categories": ["public_health", "mosquito_menace", "sanitation"],
    },
    {
        "name": "FOREST",
        "full_name": "Karnataka Forest Department",
        "categories": ["tree_cutting", "urban_forest", "wildlife_rescue"],
    },
    {
        "name": "HORTICULTURE",
        "full_name": "Department of Horticulture, Karnataka",
        "categories": ["public_garden", "landscaping", "park_maintenance"],
    },
    {
        "name": "KSDMA",
        "full_name": "Karnataka State Disaster Management Authority",
        "categories": ["flooding_emergency", "storm_damage", "disaster_response"],
    },
]

CATEGORY_TO_DEPARTMENT = {
    category: department["name"]
    for department in DEPARTMENT_CATALOG
    for category in department["categories"]
}
VALID_CATEGORIES = sorted(CATEGORY_TO_DEPARTMENT.keys()) + ["other"]


PRIORITY_RULES = {
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
    "traffic_signal": 3,
    "traffic_congestion": 3,
    "illegal_parking": 2,
    "public_transport": 2,
    "metro_station": 2,
    "illegal_construction": 2,
    "encroachment": 2,
    "park_maintenance": 1,
    "stray_animals": 2,
    "air_pollution": 4,
    "fire_hazard": 5,
    "transformer": 5,
    "cycle_track": 2,
    "mosquito_menace": 4,
    "storm_damage": 5,
    "other": 2,
}

URGENCY_KEYWORDS = {
    5: [
        "emergency",
        "danger",
        "dangerous",
        "life threatening",
        "electrocution",
        "fire",
        "collapse",
        "collapsed",
        "burst",
        "sparks",
    ],
    4: [
        "urgent",
        "severe",
        "sewage overflow",
        "accident",
        "children at risk",
        "pollution",
        "mosquito",
        "flooding",
    ],
    3: ["weeks", "months", "repeated", "no response", "multiple complaints"],
}


@dataclass
class ParsedComplaint:
    category: str
    department: str
    description: str
    location_text: Optional[str]
    severity: int
    confidence: float


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------

def category_prompt_text() -> str:
    return ", ".join(VALID_CATEGORIES)


def department_prompt_lines() -> str:
    return "\n".join(
        f"- {department['name']}: {', '.join(department['categories'])}"
        for department in DEPARTMENT_CATALOG
    )


SYSTEM_PROMPT = f"""
You are City Brain, an AI complaint classifier for Bengaluru civic governance.

Task:
Parse a citizen complaint and return a JSON object with one array named
"complaints". Each complaint must be a separate civic issue.

Rules:
1. If one message contains multiple issues, extract each issue separately.
2. Use only these categories:
   {category_prompt_text()}
3. Route each category to the correct department:
{department_prompt_lines()}
4. Extract a shared or issue-specific location if present.
5. Rate severity from 1 to 5.
6. Return confidence from 0.0 to 1.0.
7. Respond only with valid JSON. Do not include markdown or explanation.

Expected JSON:
{{
  "complaints": [
    {{
      "category": "road_damage",
      "department": "BBMP",
      "description": "Road is damaged",
      "location_text": "Jayanagar 4th Cross",
      "severity": 3,
      "confidence": 0.91
    }}
  ]
}}
""".strip()

FEW_SHOT_EXAMPLES = """
Input: "Water leakage and streetlight broken near Jayanagar 4th cross"
Output: {"complaints":[{"category":"water_leakage","department":"BWSSB","description":"Water leakage reported","location_text":"Jayanagar 4th cross","severity":4,"confidence":0.93},{"category":"streetlight","department":"BESCOM","description":"Streetlight is broken or not working","location_text":"Jayanagar 4th cross","severity":3,"confidence":0.91}]}

Input: "Signal not working garbage not collected and drainage blocked near Electronic City school"
Output: {"complaints":[{"category":"traffic_signal","department":"BTP","description":"Traffic signal is not working","location_text":"Electronic City school","severity":3,"confidence":0.9},{"category":"garbage","department":"BSWML","description":"Garbage has not been collected","location_text":"Electronic City school","severity":2,"confidence":0.9},{"category":"drainage","department":"BBMP","description":"Drainage is blocked","location_text":"Electronic City school","severity":3,"confidence":0.9}]}

Input: "Water leak streetlite off bad road garbage near HSR layout"
Output: {"complaints":[{"category":"water_leakage","department":"BWSSB","description":"Water leakage reported","location_text":"HSR layout","severity":4,"confidence":0.92},{"category":"streetlight","department":"BESCOM","description":"Streetlight is off","location_text":"HSR layout","severity":3,"confidence":0.9},{"category":"road_damage","department":"BBMP","description":"Road is damaged","location_text":"HSR layout","severity":3,"confidence":0.88},{"category":"garbage","department":"BSWML","description":"Garbage issue reported","location_text":"HSR layout","severity":2,"confidence":0.88}]}
""".strip()


# ---------------------------------------------------------------------------
# Deterministic Parsing Layer
# ---------------------------------------------------------------------------

LOCATION_PATTERN = re.compile(
    r"\b(?:in\s+front\s+of|front\s+of|opposite|outside|beside|behind|around|near|at|on|in)"
    r"\s+(?:the\s+)?([a-z0-9 .'-]+?)(?=\s+(?:and|also|but|with|due to)\b|[,.]|$)",
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


def normalize_complaint_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"[^a-z0-9\s.,'-]", " ", normalized)
    for pattern, replacement in TEXT_NORMALIZATION_REPLACEMENTS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def extract_location(text: str) -> Optional[str]:
    matches = [m.group(1).strip(" .,-") for m in LOCATION_PATTERN.finditer(text)]
    cleaned_matches = []
    for match in matches:
        cleaned = re.sub(r"^(?:front\s+of|of|our\s+area|area)\s+", "", match).strip(" .,-")
        cleaned = re.sub(r"^(?:road|street|lane|main)\s+(?:at|near|in|on)\s+", "", cleaned).strip(" .,-")
        if len(cleaned) >= 3:
            cleaned_matches.append(cleaned)
    return cleaned_matches[-1][:120] if cleaned_matches else None


def normalize_location_text(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    normalized = re.sub(r"\b(the|near|in|at|on|road|street|main)\b", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def rule_based_parse(text: str) -> list[dict[str, Any]]:
    text_lower = normalize_complaint_text(text)
    location_text = extract_location(text_lower)
    issues: list[dict[str, Any]] = []
    seen_categories: set[str] = set()

    for rule in RULE_BASED_ISSUES:
        category = rule["category"]
        if category in seen_categories:
            continue
        if any(re.search(pattern, text_lower, flags=re.IGNORECASE) for pattern in rule["patterns"]):
            seen_categories.add(category)
            issues.append({
                "category": category,
                "department": rule["department"],
                "description": rule["description"],
                "location_text": location_text,
                "severity": rule["severity"],
                "confidence": rule["confidence"],
            })

    return issues


# ---------------------------------------------------------------------------
# LLM Call + JSON Repair
# ---------------------------------------------------------------------------

def build_prompt(text: str) -> str:
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"{FEW_SHOT_EXAMPLES}\n\n"
        f"Parse this complaint:\n{text}"
    )


def extract_json_object(raw_text: str) -> dict[str, Any]:
    content = raw_text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        return json.loads(content[start:end + 1])
    raise ValueError("LLM response did not contain a JSON object")


async def call_ollama(text: str, model: str = TRAINED_MODEL_NAME) -> list[dict[str, Any]]:
    prompt = build_prompt(text)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            OLLAMA_GENERATE_URL,
            json={
                "model": model,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 768,
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        parsed = extract_json_object(payload.get("response", ""))
        complaints = parsed.get("complaints", parsed)
        return complaints if isinstance(complaints, list) else [complaints]


# ---------------------------------------------------------------------------
# Validation, Merge, Priority
# ---------------------------------------------------------------------------

def find_closest_category(category: str) -> str:
    keyword_map = {
        "road": "road_damage",
        "pothole": "pothole",
        "street light": "streetlight",
        "light": "streetlight",
        "water leak": "water_leakage",
        "leak": "water_leakage",
        "pipe": "water_leakage",
        "water": "water_supply",
        "sewer": "sewage",
        "garbage": "garbage",
        "trash": "garbage",
        "waste": "garbage",
        "drain": "drainage",
        "electric": "electricity",
        "power": "power_outage",
        "tree": "tree_fall",
        "traffic": "traffic_signal",
        "signal": "traffic_signal",
        "parking": "illegal_parking",
        "bus": "public_transport",
        "metro": "metro_station",
        "park": "park_maintenance",
        "dog": "stray_animals",
        "animal": "stray_animals",
        "construction": "illegal_construction",
        "noise": "noise_pollution",
        "encroach": "encroachment",
        "pollution": "air_pollution",
        "smoke": "air_pollution",
        "fire": "fire_hazard",
        "transformer": "transformer",
        "footpath": "footpath",
        "cycle": "cycle_track",
        "mosquito": "mosquito_menace",
        "storm": "storm_damage",
        "disaster": "disaster_response",
    }
    category_lower = category.lower()
    for keyword, resolved_category in keyword_map.items():
        if keyword in category_lower:
            return resolved_category
    return "other"


def calculate_priority(category: str, text: str) -> int:
    base = PRIORITY_RULES.get(category, 2)
    text_lower = text.lower()
    for priority_level in [5, 4, 3]:
        if any(keyword in text_lower for keyword in URGENCY_KEYWORDS.get(priority_level, [])):
            return max(base, priority_level)
    return base


def validate_and_fix(raw_complaints: list[dict[str, Any]], original_text: str) -> list[ParsedComplaint]:
    validated: list[ParsedComplaint] = []
    for raw in raw_complaints:
        if not isinstance(raw, dict):
            continue

        category = str(raw.get("category", "other")).lower().strip()
        if category not in VALID_CATEGORIES:
            category = find_closest_category(category)

        department = CATEGORY_TO_DEPARTMENT.get(category, "GENERAL")
        severity = raw.get("severity", raw.get("priority", PRIORITY_RULES.get(category, 2)))
        try:
            severity_int = max(1, min(5, int(severity)))
        except (TypeError, ValueError):
            severity_int = PRIORITY_RULES.get(category, 2)

        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.65))))
        except (TypeError, ValueError):
            confidence = 0.65

        description = raw.get("description") or raw.get("summary") or original_text[:180]
        location_text = raw.get("location_text") or extract_location(normalize_complaint_text(original_text))

        validated.append(ParsedComplaint(
            category=category,
            department=department,
            description=str(description),
            location_text=location_text,
            severity=severity_int,
            confidence=confidence,
        ))

    return validated


def merge_parser_results(
    llm_complaints: list[ParsedComplaint],
    rule_complaints: list[ParsedComplaint],
) -> list[ParsedComplaint]:
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


# ---------------------------------------------------------------------------
# Public Entry Points
# ---------------------------------------------------------------------------

async def parse_complaint(text: str, language: str = "en", use_llm: bool = True) -> dict[str, Any]:
    """
    Classify a civic complaint into one or more department-specific tickets.

    The deterministic parser always runs first for demo reliability. The
    trained model is used as an enrichment layer when Ollama is available.
    """
    normalized_text = normalize_complaint_text(text)
    rule_complaints = validate_and_fix(rule_based_parse(normalized_text), text)

    llm_complaints: list[ParsedComplaint] = []
    if use_llm:
        for model_name in [TRAINED_MODEL_NAME, FALLBACK_MODEL_NAME]:
            try:
                raw_llm = await call_ollama(normalized_text, model=model_name)
                llm_complaints = validate_and_fix(raw_llm, text)
                if llm_complaints:
                    break
            except Exception as exc:
                logger.warning("Model call failed for %s: %s", model_name, exc)

    complaints = merge_parser_results(llm_complaints, rule_complaints)
    if not complaints:
        complaints = [ParsedComplaint(
            category="other",
            department="GENERAL",
            description=text[:180],
            location_text=extract_location(normalized_text),
            severity=2,
            confidence=0.35,
        )]

    for complaint in complaints:
        complaint.severity = calculate_priority(complaint.category, text)

    return {
        "original_text": text,
        "normalized_text": normalized_text,
        "detected_language": language,
        "model": TRAINED_MODEL_NAME if use_llm else "rule_based_only",
        "complaints": [asdict(complaint) for complaint in complaints],
        "total_complaints_detected": len(complaints),
    }


async def classify_complaint(text: str, language: str = "en") -> list[dict[str, Any]]:
    """Compatibility entry point for services that expect only the list."""
    result = await parse_complaint(text=text, language=language, use_llm=True)
    return result["complaints"]


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------

async def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="City Brain model-kit complaint parser")
    parser.add_argument("text", nargs="*", help="Complaint text to classify")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic parser only")
    args = parser.parse_args()

    text = " ".join(args.text).strip()
    if not text:
        text = "water leak streetlite off bad road garbage near hsr layout"

    result = await parse_complaint(text, use_llm=not args.no_llm)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_cli())
