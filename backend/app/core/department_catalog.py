"""City Brain civic organization catalog for Bengaluru demos."""

DEPARTMENT_CATALOG = [
    {
        "name": "BBMP",
        "full_name": "Bruhat Bengaluru Mahanagara Palike",
        "description": "Municipal corporation - roads, drainage, parks, buildings, civic maintenance",
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
        "description": "Power supply, local electrical faults, streetlights, and outages",
        "categories": ["streetlight", "electricity", "power_outage"],
    },
    {
        "name": "BWSSB",
        "full_name": "Bangalore Water Supply and Sewerage Board",
        "description": "Water supply, leakage, sewer network, and sanitation lines",
        "categories": ["water_supply", "water_leakage"],
    },
    {
        "name": "BTP",
        "full_name": "Bengaluru Traffic Police",
        "description": "Traffic signals, congestion, road safety, and traffic enforcement",
        "categories": ["traffic_signal", "traffic_congestion", "illegal_parking"],
    },
    {
        "name": "BMTC",
        "full_name": "Bangalore Metropolitan Transport Corporation",
        "description": "Public bus transport services, stops, shelters, and routes",
        "categories": ["public_transport", "bus_stop", "bus_service"],
    },
    {
        "name": "BMRCL",
        "full_name": "Bangalore Metro Rail Corporation Limited",
        "description": "Metro stations, metro access, and Namma Metro service issues",
        "categories": ["metro_service", "metro_station", "metro_access"],
    },
    {
        "name": "BDA",
        "full_name": "Bangalore Development Authority",
        "description": "Urban planning, layouts, development works, and BDA properties",
        "categories": ["layout_issue", "land_use", "development_work"],
    },
    {
        "name": "BSWML",
        "full_name": "Bengaluru Solid Waste Management Limited",
        "description": "Solid waste collection, waste processing, and black spot clearance",
        "categories": ["garbage", "solid_waste", "waste_collection"],
    },
    {
        "name": "KSPCB",
        "full_name": "Karnataka State Pollution Control Board",
        "description": "Air, water, industrial, and environmental pollution complaints",
        "categories": ["air_pollution", "water_pollution", "industrial_pollution"],
    },
    {
        "name": "KSFES",
        "full_name": "Karnataka State Fire and Emergency Services",
        "description": "Fire hazards, unsafe buildings, and emergency response",
        "categories": ["fire_hazard", "fire_emergency", "building_safety"],
    },
    {
        "name": "KPTCL",
        "full_name": "Karnataka Power Transmission Corporation Limited",
        "description": "High-voltage transmission lines, substations, and transformers",
        "categories": ["transmission_line", "transformer", "substation"],
    },
    {
        "name": "PWD",
        "full_name": "Public Works Department, Karnataka",
        "description": "State roads, public buildings, and major public works",
        "categories": ["state_road", "public_building", "bridge_damage"],
    },
    {
        "name": "RTO",
        "full_name": "Regional Transport Office Bengaluru",
        "description": "Vehicle enforcement, transport permits, road transport issues",
        "categories": ["vehicle_violation", "vehicle_pollution", "transport_permit"],
    },
    {
        "name": "DULT",
        "full_name": "Directorate of Urban Land Transport",
        "description": "Footpaths, cycling, pedestrian access, and urban mobility",
        "categories": ["footpath", "cycle_track", "pedestrian_access"],
    },
    {
        "name": "KSP",
        "full_name": "Bengaluru City Police",
        "description": "Public safety, nuisance, and law-and-order support",
        "categories": ["public_safety", "law_order", "public_nuisance"],
    },
    {
        "name": "BBMP_HEALTH",
        "full_name": "BBMP Health Department",
        "description": "Public health, mosquito control, sanitation, and disease prevention",
        "categories": ["public_health", "mosquito_menace", "sanitation"],
    },
    {
        "name": "FOREST",
        "full_name": "Karnataka Forest Department",
        "description": "Tree cutting, urban forest protection, and wildlife rescue",
        "categories": ["tree_cutting", "urban_forest", "wildlife_rescue"],
    },
    {
        "name": "HORTICULTURE",
        "full_name": "Department of Horticulture, Karnataka",
        "description": "Public gardens, landscaping, and horticulture maintenance",
        "categories": ["public_garden", "landscaping", "park_maintenance"],
    },
    {
        "name": "KSDMA",
        "full_name": "Karnataka State Disaster Management Authority",
        "description": "Flooding, storm damage, disaster alerts, and emergency coordination",
        "categories": ["flooding_emergency", "storm_damage", "disaster_response"],
    },
]

CATEGORY_TO_DEPARTMENT = {
    category: department["name"]
    for department in DEPARTMENT_CATALOG
    for category in department["categories"]
}

VALID_CATEGORIES = sorted(CATEGORY_TO_DEPARTMENT.keys()) + ["other"]


def category_prompt_text() -> str:
    return ", ".join(VALID_CATEGORIES)


def department_prompt_lines() -> str:
    return "\n".join(
        f"   - {department['name']}: {', '.join(department['categories'])}"
        for department in DEPARTMENT_CATALOG
    )
