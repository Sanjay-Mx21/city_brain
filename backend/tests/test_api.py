import struct
import zlib

import pytest

from app.core.config import Settings



GARBAGE_TEXT = "Garbage has not been collected for a week near Jayanagar 4th block market"


def tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"\x00" + b"\x00\x00\x00"
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


async def register(client, phone="+919876543210", password="goodpass123"):
    res = await client.post("/api/v1/auth/register", json={
        "full_name": "Test Citizen", "phone": phone, "password": password,
    })
    return res


async def citizen_headers(client, phone="+919876543210"):
    res = await register(client, phone)
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def submit(client, headers, text=GARBAGE_TEXT):
    res = await client.post("/api/v1/complaints/submit", headers=headers, json={
        "text": text, "latitude": 12.93, "longitude": 77.58, "language": "en",
    })
    assert res.status_code == 200, res.text
    return res.json()["tickets"][0]


async def test_health(client):
    assert (await client.get("/health")).json() == {"status": "healthy"}
    assert (await client.get("/")).status_code == 200


async def test_register_login_me(client):
    headers = await citizen_headers(client)
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["role"] == "citizen"

    login = await client.post("/api/v1/auth/login", json={"phone": "+919876543210", "password": "goodpass123"})
    assert login.status_code == 200
    bad = await client.post("/api/v1/auth/login", json={"phone": "+919876543210", "password": "wrongpass"})
    assert bad.status_code == 401
    dup = await register(client)
    assert dup.status_code == 409


async def test_short_password_rejected(client):
    assert (await register(client, password="abc123")).status_code == 422


async def test_auth_required(client):
    assert (await client.get("/api/v1/complaints/my")).status_code in (401, 403)
    assert (await client.get("/api/v1/admin/dashboard")).status_code in (401, 403)


async def test_login_rate_limited(client):
    codes = []
    for _ in range(12):
        res = await client.post("/api/v1/auth/login", json={"phone": "+910", "password": "whatever1"})
        codes.append(res.status_code)
    assert 429 in codes


async def test_submit_and_list_complaint(client):
    headers = await citizen_headers(client)
    ticket = await submit(client, headers)
    assert ticket["ticket_id"].startswith("CB-")
    assert ticket["category"] == "garbage"
    assert ticket["department_name"] == "BBMP"

    mine = await client.get("/api/v1/complaints/my", headers=headers)
    assert mine.status_code == 200 and mine.json()["total"] == 1


async def test_public_track_hides_private_fields(client):
    headers = await citizen_headers(client)
    ticket = await submit(client, headers)
    tid = ticket["ticket_id"]

    public = (await client.get(f"/api/v1/complaints/track/{tid}")).json()
    assert public["status"] == "pending"
    assert public["original_text"] == ""
    assert public["latitude"] is None and public["longitude"] is None

    owner = (await client.get(f"/api/v1/complaints/track/{tid}", headers=headers)).json()
    assert owner["original_text"] == GARBAGE_TEXT
    assert owner["latitude"] == 12.93

    other = await citizen_headers(client, phone="+919000000009")
    stranger = (await client.get(f"/api/v1/complaints/track/{tid}", headers=other)).json()
    assert stranger["original_text"] == ""

    assert (await client.get("/api/v1/complaints/track/CB-2026-99999")).status_code == 404


async def test_image_upload_valid_png(client):
    headers = await citizen_headers(client)
    ticket = await submit(client, headers)
    res = await client.post(
        f"/api/v1/complaints/{ticket['id']}/image", headers=headers,
        files={"file": ("photo.html", tiny_png(), "text/html")},
    )
    assert res.status_code == 200, res.text
    url = res.json()["image_url"]
    assert url.endswith(".png"), "extension must come from file signature, not filename"

    served = await client.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"


async def test_image_upload_rejects_disguised_html(client):
    headers = await citizen_headers(client)
    ticket = await submit(client, headers)
    res = await client.post(
        f"/api/v1/complaints/{ticket['id']}/image", headers=headers,
        files={"file": ("evil.png", b"<html><script>alert(1)</script></html>", "image/png")},
    )
    assert res.status_code == 400


async def test_image_upload_size_limit(client):
    headers = await citizen_headers(client)
    ticket = await submit(client, headers)
    big = tiny_png() + b"\x00" * (1024 * 1024 + 10)
    res = await client.post(
        f"/api/v1/complaints/{ticket['id']}/image", headers=headers,
        files={"file": ("big.png", big, "image/png")},
    )
    assert res.status_code == 413


async def test_image_upload_other_citizen_forbidden(client):
    owner = await citizen_headers(client)
    ticket = await submit(client, owner)
    other = await citizen_headers(client, phone="+919000000009")
    res = await client.post(
        f"/api/v1/complaints/{ticket['id']}/image", headers=other,
        files={"file": ("p.png", tiny_png(), "image/png")},
    )
    assert res.status_code == 403


async def test_officer_department_restriction(client, staff):
    headers = await citizen_headers(client)
    ticket = await submit(client, headers)  # BBMP complaint
    url = f"/api/v1/officer/complaints/{ticket['id']}/status"

    wrong_dept = await client.patch(url, headers=staff["bescom_officer"], json={"status": "in_progress"})
    assert wrong_dept.status_code == 403

    right_dept = await client.patch(url, headers=staff["bbmp_officer"], json={"status": "in_progress"})
    assert right_dept.status_code == 200, right_dept.text

    admin = await client.patch(url, headers=staff["admin"], json={"status": "resolved", "notes": "Cleared"})
    assert admin.status_code == 200

    citizen = await client.patch(url, headers=headers, json={"status": "closed"})
    assert citizen.status_code == 403

    missing = await client.patch("/api/v1/officer/complaints/9999/status",
                                 headers=staff["bbmp_officer"], json={"status": "resolved"})
    assert missing.status_code == 404


async def test_officer_and_admin_views(client, staff):
    headers = await citizen_headers(client)
    await submit(client, headers)

    queue = await client.get("/api/v1/officer/queue", headers=staff["bbmp_officer"])
    assert queue.status_code == 200 and queue.json()["total"] == 1
    stats = await client.get("/api/v1/officer/stats", headers=staff["bbmp_officer"])
    assert stats.status_code == 200 and stats.json()["pending"] == 1

    dash = await client.get("/api/v1/admin/dashboard", headers=staff["admin"])
    assert dash.status_code == 200 and dash.json()["total_complaints"] == 1
    assert (await client.get("/api/v1/admin/dashboard", headers=staff["bbmp_officer"])).status_code == 403
    assert (await client.get("/api/v1/admin/heatmap", headers=staff["admin"])).status_code == 200
    assert (await client.get("/api/v1/admin/departments")).status_code == 200
    assert (await client.get("/api/v1/admin/wards")).status_code == 200


async def test_assistant_chat(client):
    headers = await citizen_headers(client)
    res = await client.post("/api/v1/assistant/chat", headers=headers, json={"message": "how do I track status"})
    assert res.status_code == 200 and res.json()["intent"] == "status_help"


async def test_whatsapp_disabled(client):
    res = await client.post("/api/v1/whatsapp/webhook", data={"From": "whatsapp:+911", "Body": "hi"})
    assert res.status_code == 404


def test_production_rejects_insecure_defaults():
    with pytest.raises(RuntimeError):
        Settings(_env_file=None, APP_ENV="production", DEBUG=False).validate_for_production()
    strong = "x" * 40
    Settings(_env_file=None, APP_ENV="production", DEBUG=False,
             JWT_SECRET=strong, SECRET_KEY=strong).validate_for_production()


def test_cors_origins_in_production():
    s = Settings(_env_file=None, APP_ENV="production", FRONTEND_URL="https://city.example.com/",
                 CORS_ORIGINS="https://admin.example.com")
    assert s.cors_origins == ["https://admin.example.com", "https://city.example.com"]
