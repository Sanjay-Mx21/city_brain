"""
City Brain seed data.
Creates departments, wards, demo users, and synthetic complaints for local demos.
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal, Base, engine
from app.core.department_catalog import DEPARTMENT_CATALOG
from app.core.schema_updates import ensure_local_schema_updates
from app.core.security import hash_password
from app.models.models import (
    Complaint,
    ComplaintStatus,
    Department,
    Officer,
    User,
    UserRole,
    Ward,
)


DEPARTMENTS = DEPARTMENT_CATALOG


WARDS = [
    {"ward_number": 1, "name": "Kempegowda Ward", "zone": "East", "lat": 12.9716, "lon": 77.5946},
    {"ward_number": 2, "name": "Jayanagar", "zone": "South", "lat": 12.9308, "lon": 77.5838},
    {"ward_number": 3, "name": "Koramangala", "zone": "South-East", "lat": 12.9352, "lon": 77.6245},
    {"ward_number": 4, "name": "Indiranagar", "zone": "East", "lat": 12.9784, "lon": 77.6408},
    {"ward_number": 5, "name": "Malleshwaram", "zone": "West", "lat": 13.0035, "lon": 77.5687},
    {"ward_number": 6, "name": "Rajajinagar", "zone": "West", "lat": 12.9910, "lon": 77.5530},
    {"ward_number": 7, "name": "Basavanagudi", "zone": "South", "lat": 12.9422, "lon": 77.5742},
    {"ward_number": 8, "name": "Whitefield", "zone": "East", "lat": 12.9698, "lon": 77.7500},
    {"ward_number": 9, "name": "Electronic City", "zone": "South", "lat": 12.8456, "lon": 77.6603},
    {"ward_number": 10, "name": "HSR Layout", "zone": "South-East", "lat": 12.9121, "lon": 77.6446},
    {"ward_number": 11, "name": "BTM Layout", "zone": "South", "lat": 12.9166, "lon": 77.6101},
    {"ward_number": 12, "name": "Marathahalli", "zone": "East", "lat": 12.9591, "lon": 77.6974},
    {"ward_number": 13, "name": "Hebbal", "zone": "North", "lat": 13.0358, "lon": 77.5970},
    {"ward_number": 14, "name": "Yelahanka", "zone": "North", "lat": 13.1005, "lon": 77.5963},
    {"ward_number": 15, "name": "Banashankari", "zone": "South", "lat": 12.9255, "lon": 77.5468},
    {"ward_number": 16, "name": "JP Nagar", "zone": "South", "lat": 12.9063, "lon": 77.5857},
    {"ward_number": 17, "name": "Vijayanagar", "zone": "West", "lat": 12.9719, "lon": 77.5362},
    {"ward_number": 18, "name": "Majestic", "zone": "Central", "lat": 12.9767, "lon": 77.5713},
    {"ward_number": 19, "name": "Shivajinagar", "zone": "Central", "lat": 12.9857, "lon": 77.6057},
    {"ward_number": 20, "name": "RT Nagar", "zone": "North", "lat": 13.0210, "lon": 77.5970},
    {"ward_number": 21, "name": "Peenya", "zone": "North-West", "lat": 13.0297, "lon": 77.5197},
    {"ward_number": 22, "name": "Bommanahalli", "zone": "South-East", "lat": 12.9010, "lon": 77.6186},
    {"ward_number": 23, "name": "Bellandur", "zone": "South-East", "lat": 12.9260, "lon": 77.6762},
    {"ward_number": 24, "name": "Sarjapur Road", "zone": "South-East", "lat": 12.9107, "lon": 77.6871},
    {"ward_number": 25, "name": "Kengeri", "zone": "South-West", "lat": 12.9075, "lon": 77.4823},
    {"ward_number": 26, "name": "Yeshwanthpur", "zone": "North-West", "lat": 13.0220, "lon": 77.5440},
    {"ward_number": 27, "name": "Nagarbhavi", "zone": "West", "lat": 12.9617, "lon": 77.5103},
    {"ward_number": 28, "name": "Domlur", "zone": "East", "lat": 12.9607, "lon": 77.6387},
    {"ward_number": 29, "name": "Frazer Town", "zone": "Central", "lat": 12.9973, "lon": 77.6138},
    {"ward_number": 30, "name": "Sadashivanagar", "zone": "North", "lat": 13.0073, "lon": 77.5810},
]


SAMPLE_COMPLAINTS = [
    {"text": "Huge pothole on 80 feet road near Koramangala", "category": "pothole", "dept": "BBMP", "priority": 3},
    {"text": "Streetlight not working for 2 weeks in Jayanagar 4th Block", "category": "streetlight", "dept": "BESCOM", "priority": 3},
    {"text": "No water supply since 3 days in Indiranagar", "category": "water_supply", "dept": "BWSSB", "priority": 4},
    {"text": "Garbage dump on main road in BTM Layout", "category": "garbage", "dept": "BBMP", "priority": 2},
    {"text": "Drainage overflow causing flooding in HSR Layout", "category": "drainage", "dept": "BBMP", "priority": 4},
    {"text": "Road completely damaged near Whitefield railway crossing", "category": "road_damage", "dept": "BBMP", "priority": 3},
    {"text": "Water pipe burst on MG Road creating emergency", "category": "water_leakage", "dept": "BWSSB", "priority": 5},
    {"text": "Power outage in entire Marathahalli area for 6 hours", "category": "power_outage", "dept": "BESCOM", "priority": 4},
    {"text": "Big tree fallen on road in Malleshwaram blocking traffic", "category": "tree_fall", "dept": "BBMP", "priority": 5},
    {"text": "Illegal construction happening next to my house in Rajajinagar", "category": "illegal_construction", "dept": "BBMP", "priority": 2},
    {"text": "Traffic signal broken at Hebbal flyover junction", "category": "traffic_signal", "dept": "BTP", "priority": 3},
    {"text": "Stray dog menace near children's park in Basavanagudi", "category": "stray_animals", "dept": "BBMP", "priority": 3},
    {"text": "Sewage overflow on street in Electronic City Phase 1", "category": "sewage", "dept": "BBMP", "priority": 4},
    {"text": "Park in JP Nagar not maintained, broken benches", "category": "park_maintenance", "dept": "BBMP", "priority": 1},
    {"text": "Construction noise at midnight in Bellandur", "category": "noise_pollution", "dept": "BBMP", "priority": 2},
    {"text": "Bus stop shelter collapsed in Peenya", "category": "public_transport", "dept": "BMTC", "priority": 3},
    {"text": "Footpath encroached by shops in Shivajinagar", "category": "encroachment", "dept": "BBMP", "priority": 2},
    {"text": "Multiple potholes on Sarjapur Road very dangerous", "category": "pothole", "dept": "BBMP", "priority": 4},
    {"text": "Electricity wire hanging dangerously low in RT Nagar", "category": "electricity", "dept": "BESCOM", "priority": 5},
    {"text": "No water pressure in Banashankari, problem for weeks", "category": "water_supply", "dept": "BWSSB", "priority": 3},
    {"text": "Metro station escalator not working near Indiranagar", "category": "metro_station", "dept": "BMRCL", "priority": 2},
    {"text": "BDA layout road work left incomplete in Nagarbhavi", "category": "development_work", "dept": "BDA", "priority": 2},
    {"text": "Garbage collection vehicle has not come for 4 days in JP Nagar", "category": "waste_collection", "dept": "BSWML", "priority": 3},
    {"text": "Factory smoke causing air pollution near Peenya", "category": "air_pollution", "dept": "KSPCB", "priority": 4},
    {"text": "Fire safety violation in commercial building at Majestic", "category": "fire_hazard", "dept": "KSFES", "priority": 5},
    {"text": "Transformer sparks near Yelahanka substation", "category": "transformer", "dept": "KPTCL", "priority": 5},
    {"text": "State road bridge side wall damaged near Kengeri", "category": "bridge_damage", "dept": "PWD", "priority": 4},
    {"text": "Autos parked illegally blocking road near Shivajinagar", "category": "vehicle_violation", "dept": "RTO", "priority": 2},
    {"text": "Cycle track blocked by debris in HSR Layout", "category": "cycle_track", "dept": "DULT", "priority": 2},
    {"text": "Public nuisance and safety issue near Frazer Town", "category": "public_safety", "dept": "KSP", "priority": 3},
    {"text": "Mosquito breeding due to stagnant water in Bellandur", "category": "mosquito_menace", "dept": "BBMP_HEALTH", "priority": 4},
    {"text": "Unauthorized tree cutting reported in Sadashivanagar", "category": "tree_cutting", "dept": "FOREST", "priority": 4},
    {"text": "Public garden plants drying due to poor maintenance in Lalbagh area", "category": "public_garden", "dept": "HORTICULTURE", "priority": 2},
    {"text": "Storm damage and flooding emergency near Bommanahalli", "category": "storm_damage", "dept": "KSDMA", "priority": 5},
]

LOCATION_DETAILS = [
    "near the bus stop",
    "beside the market",
    "outside the school",
    "near the metro station",
    "at 1st main",
    "at 4th cross",
    "near the park entrance",
    "beside the apartment gate",
    "near the hospital road",
    "at the main junction",
]

CATEGORY_TEMPLATES = {
    "pothole": [
        "Large pothole causing slow traffic {location}",
        "Deep pothole filled with rainwater {location}",
        "Multiple potholes damaging vehicles {location}",
    ],
    "streetlight": [
        "Streetlight is not working {location}",
        "Streetlight pole is damaged and dark at night {location}",
        "Broken streetlight causing safety concerns {location}",
    ],
    "water_supply": [
        "No water supply since morning {location}",
        "Very low water pressure reported {location}",
        "Water supply interrupted for multiple houses {location}",
    ],
    "garbage": [
        "Garbage pile has not been cleared {location}",
        "Overflowing waste bin causing bad smell {location}",
        "Uncollected garbage blocking the footpath {location}",
    ],
    "drainage": [
        "Drainage blockage causing waterlogging {location}",
        "Storm water drain is overflowing {location}",
        "Blocked drain after rain causing flooding {location}",
    ],
    "road_damage": [
        "Road surface is damaged and uneven {location}",
        "Road has broken patches causing vehicle damage {location}",
        "Damaged road needs urgent repair {location}",
    ],
    "water_leakage": [
        "Water pipe leakage wasting water {location}",
        "Water pipe burst flooding the road {location}",
        "Continuous water leakage from underground pipe {location}",
    ],
    "power_outage": [
        "Power outage affecting houses {location}",
        "Electricity supply is unstable {location}",
        "Frequent power cuts reported {location}",
    ],
    "electricity": [
        "Electric wire is hanging dangerously {location}",
        "Electrical box is open and unsafe {location}",
        "Sparking electricity line reported {location}",
    ],
    "tree_fall": [
        "Tree branch has fallen and blocked the road {location}",
        "Large tree is leaning dangerously {location}",
        "Fallen tree needs immediate clearance {location}",
    ],
    "illegal_construction": [
        "Unauthorized construction activity noticed {location}",
        "Building material is blocking public space {location}",
        "Illegal construction work is continuing {location}",
    ],
    "traffic_signal": [
        "Traffic signal is not working {location}",
        "Signal timing issue causing congestion {location}",
        "Broken traffic signal creating confusion {location}",
    ],
    "stray_animals": [
        "Stray animal problem reported {location}",
        "Stray dogs chasing pedestrians {location}",
        "Animal menace near residential lane {location}",
    ],
    "sewage": [
        "Sewage overflow causing bad smell {location}",
        "Sewage water flowing on the street {location}",
        "Manhole overflow needs urgent attention {location}",
    ],
    "park_maintenance": [
        "Park equipment is broken {location}",
        "Park lights and benches need maintenance {location}",
        "Children's play area is not maintained {location}",
    ],
    "noise_pollution": [
        "Loud construction noise late at night {location}",
        "Noise pollution disturbing residents {location}",
        "Loudspeaker noise reported repeatedly {location}",
    ],
    "public_transport": [
        "Bus stop shelter is damaged {location}",
        "BMTC bus stop needs repair {location}",
        "Public transport shelter is unsafe {location}",
    ],
    "encroachment": [
        "Footpath encroachment blocking pedestrians {location}",
        "Shops have occupied public walkway {location}",
        "Encroachment causing traffic bottleneck {location}",
    ],
    "metro_station": [
        "Metro station escalator is not working {location}",
        "Metro station access is blocked {location}",
        "Namma Metro station facility needs repair {location}",
    ],
    "development_work": [
        "Development work has been left incomplete {location}",
        "BDA layout work is blocking access {location}",
        "Open development trench needs barricading {location}",
    ],
    "waste_collection": [
        "Waste collection has been missed repeatedly {location}",
        "Door-to-door garbage collection has not happened {location}",
        "Solid waste collection point is overflowing {location}",
    ],
    "air_pollution": [
        "Air pollution from smoke reported {location}",
        "Industrial smoke causing breathing issues {location}",
        "Dust and smoke pollution needs inspection {location}",
    ],
    "fire_hazard": [
        "Fire safety hazard reported {location}",
        "Unsafe electrical setup could cause fire {location}",
        "Emergency fire-risk inspection needed {location}",
    ],
    "transformer": [
        "Transformer is sparking dangerously {location}",
        "Transformer oil leak reported {location}",
        "Substation transformer needs urgent inspection {location}",
    ],
    "bridge_damage": [
        "Bridge side wall is damaged {location}",
        "Bridge approach road is unsafe {location}",
        "Public bridge structure needs repair {location}",
    ],
    "vehicle_violation": [
        "Vehicle violation is blocking public access {location}",
        "Autos and vehicles are parked illegally {location}",
        "Transport enforcement needed for blocked road {location}",
    ],
    "cycle_track": [
        "Cycle track is blocked by debris {location}",
        "Cycle lane marking is damaged {location}",
        "Unsafe cycling path needs repair {location}",
    ],
    "public_safety": [
        "Public safety issue reported {location}",
        "Residents reported nuisance and safety risk {location}",
        "Police support needed for public disturbance {location}",
    ],
    "mosquito_menace": [
        "Mosquito breeding reported due to stagnant water {location}",
        "Public health inspection needed for mosquito menace {location}",
        "Sanitation issue causing mosquito problem {location}",
    ],
    "tree_cutting": [
        "Unauthorized tree cutting reported {location}",
        "Urban tree damage needs forest department inspection {location}",
        "Tree protection complaint raised {location}",
    ],
    "public_garden": [
        "Public garden maintenance is poor {location}",
        "Garden plants and landscaping need maintenance {location}",
        "Horticulture issue reported in public garden {location}",
    ],
    "storm_damage": [
        "Storm damage requires emergency response {location}",
        "Heavy rain damage reported {location}",
        "Disaster response needed after storm {location}",
    ],
    "other": [
        "General civic issue reported {location}",
        "Citizen reported a local civic problem {location}",
        "Public service issue needs review {location}",
    ],
}

MIN_SEED_COMPLAINTS = 1500
MAX_SEED_COMPLAINTS = 5000
DEFAULT_SEED_COMPLAINTS = 1500
SLA_HOURS = {1: 720, 2: 168, 3: 72, 4: 24, 5: 4}


def get_seed_complaint_target() -> int:
    raw_target = os.getenv("CITYBRAIN_SEED_COMPLAINTS", str(DEFAULT_SEED_COMPLAINTS))
    try:
        requested = int(raw_target)
    except ValueError:
        requested = DEFAULT_SEED_COMPLAINTS
    return max(MIN_SEED_COMPLAINTS, min(MAX_SEED_COMPLAINTS, requested))


def random_complaint(ticket_number: int, citizen: User, ward: Ward, dept: Department, sample: dict, status: str) -> Complaint:
    created = datetime.utcnow() - timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
    )
    resolved_at = None
    if status == ComplaintStatus.RESOLVED.value:
        resolved_at = created + timedelta(hours=random.randint(2, 120))

    location = f"{ward.name}, {random.choice(LOCATION_DETAILS)}"
    templates = CATEGORY_TEMPLATES.get(sample["category"], [sample["text"] + " {location}"])
    description = random.choice(templates).format(location=f"at {location}")

    return Complaint(
        ticket_id=f"CB-2026-{ticket_number:05d}",
        citizen_id=citizen.id,
        original_text=description,
        original_language="en",
        category=sample["category"],
        description=description,
        location_text=location,
        latitude=ward.latitude + random.uniform(-0.005, 0.005),
        longitude=ward.longitude + random.uniform(-0.005, 0.005),
        department_id=dept.id,
        ward_id=ward.id,
        priority=sample["priority"],
        ai_confidence=round(random.uniform(0.75, 0.98), 2),
        status=status,
        created_at=created,
        sla_deadline=created + timedelta(hours=SLA_HOURS.get(sample["priority"], 72)),
        resolved_at=resolved_at,
    )


async def seed():
    print("Seeding City Brain database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_local_schema_updates(conn)

    async with AsyncSessionLocal() as db:
        existing_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
        if existing_users:
            departments = (await db.execute(select(Department))).scalars().all()
            dept_objects = {dept.name: dept for dept in departments}
            for dept_data in DEPARTMENTS:
                dept = dept_objects.get(dept_data["name"])
                if dept:
                    dept.full_name = dept_data["full_name"]
                    dept.description = dept_data["description"]
                    dept.categories = json.dumps(dept_data["categories"])
                    dept.is_active = True
                else:
                    dept = Department(
                        name=dept_data["name"],
                        full_name=dept_data["full_name"],
                        description=dept_data["description"],
                        categories=json.dumps(dept_data["categories"]),
                    )
                    db.add(dept)
                    await db.flush()
                    dept_objects[dept.name] = dept
            wards = (await db.execute(select(Ward))).scalars().all()
            citizen_users = (
                (await db.execute(select(User).where(User.role == UserRole.CITIZEN.value)))
                .scalars()
                .all()
            )
            demo_citizen = (
                await db.execute(select(User).where(User.phone == "+919888000000"))
            ).scalar_one_or_none()
            if demo_citizen:
                demo_citizen.preferred_language = "en"
            print(f"  Database already has users; synced {len(DEPARTMENTS)} organizations")
        else:
            dept_objects = {}
            for dept_data in DEPARTMENTS:
                dept = Department(
                    name=dept_data["name"],
                    full_name=dept_data["full_name"],
                    description=dept_data["description"],
                    categories=json.dumps(dept_data["categories"]),
                )
                db.add(dept)
                await db.flush()
                dept_objects[dept.name] = dept
            print(f"  {len(DEPARTMENTS)} departments created")

            ward_objects = {}
            for ward_data in WARDS:
                ward = Ward(
                    ward_number=ward_data["ward_number"],
                    name=ward_data["name"],
                    zone=ward_data["zone"],
                    latitude=ward_data["lat"],
                    longitude=ward_data["lon"],
                )
                db.add(ward)
                await db.flush()
                ward_objects[ward.name] = ward
            print(f"  {len(WARDS)} wards created")

            admin_user = User(
                full_name="City Admin",
                phone="+919999900000",
                email="admin@citybrain.in",
                password_hash=hash_password("admin123"),
                role=UserRole.ADMIN.value,
            )
            db.add(admin_user)
            await db.flush()

            officer_users = []
            for index, (dept_name, dept) in enumerate(dept_objects.items(), start=1):
                officer_user = User(
                    full_name=f"Officer - {dept_name}",
                    phone=f"+91999990000{index}",
                    email=f"officer.{dept_name.lower()}@citybrain.in",
                    password_hash=hash_password("officer123"),
                    role=UserRole.OFFICER.value,
                )
                db.add(officer_user)
                await db.flush()

                db.add(
                    Officer(
                        user_id=officer_user.id,
                        department_id=dept.id,
                        designation=f"Ward Officer - {dept_name}",
                    )
                )
                officer_users.append(officer_user)

            citizen_users = []
            citizen_names = [
                "Ramesh Kumar",
                "Priya Sharma",
                "Suresh Gowda",
                "Lakshmi Devi",
                "Arun Reddy",
                "Meena Iyer",
                "Karthik Nair",
                "Deepa Rao",
                "Venkatesh M",
                "Ananya Prasad",
            ]
            wards = list(ward_objects.values())
            for index, name in enumerate(citizen_names):
                citizen = User(
                    full_name=name,
                    phone=f"+91988800{index:04d}",
                    password_hash=hash_password("citizen123"),
                    role=UserRole.CITIZEN.value,
                    preferred_language="en" if index == 0 else random.choice(["en", "kn", "hi"]),
                    ward_id=random.choice(wards).id,
                )
                db.add(citizen)
                await db.flush()
                citizen_users.append(citizen)
            print(f"  1 admin + {len(officer_users)} officers + {len(citizen_users)} citizens created")

        statuses = [
            ComplaintStatus.PENDING.value,
            ComplaintStatus.ASSIGNED.value,
            ComplaintStatus.IN_PROGRESS.value,
            ComplaintStatus.RESOLVED.value,
            ComplaintStatus.ESCALATED.value,
        ]

        target_complaints = get_seed_complaint_target()
        existing_complaints = (await db.execute(select(func.count(Complaint.id)))).scalar() or 0
        max_complaint_id = (await db.execute(select(func.max(Complaint.id)))).scalar() or 0
        complaints_to_create = max(0, target_complaints - existing_complaints)

        if existing_complaints > MAX_SEED_COMPLAINTS:
            print(f"  Complaint count is {existing_complaints}, already above the max target of {MAX_SEED_COMPLAINTS}")
        elif complaints_to_create == 0:
            print(f"  Complaint count is already {existing_complaints}, within the requested range")

        for index in range(complaints_to_create):
            sample = random.choice(SAMPLE_COMPLAINTS)
            ward = random.choice(wards)
            citizen = random.choice(citizen_users)
            status = random.choice(statuses)
            dept = dept_objects.get(sample["dept"], dept_objects["BBMP"])
            db.add(random_complaint(max_complaint_id + index + 1, citizen, ward, dept, sample, status))

        if complaints_to_create:
            print(f"  {complaints_to_create} synthetic complaints created")
            print(f"  Total complaints after seed: {target_complaints}")

        await db.commit()

    print("\nSeed complete! Test accounts:")
    print("  Admin:   +919999900000 / admin123")
    print("  Officer: +919999900001 / officer123")
    print("  Citizen: +919888000000 / citizen123")


if __name__ == "__main__":
    asyncio.run(seed())
