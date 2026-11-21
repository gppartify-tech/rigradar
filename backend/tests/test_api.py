"""HTTP API tests (auth, catalog, wishlist, notifications, marketplace, builder, chat)."""
import io

from PIL import Image

from tests.conftest import register


def test_register_login_me(client):
    headers = register(client, "layla")
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["username"] == "layla" and me["is_admin"] is False
    assert client.post("/api/auth/login", json={"login": "LAYLA", "password": "supersecret1"}).status_code == 200
    assert client.post("/api/auth/login", json={"login": "layla", "password": "wrong"}).status_code == 401
    dup = client.post("/api/auth/register", json={"email": "layla@example.com", "username": "other", "password": "supersecret1"})
    assert dup.status_code == 409
    assert client.get("/api/auth/me").status_code == 401


def test_catalog_endpoints(client, catalog):
    cats = {c["slug"]: c for c in client.get("/api/categories").json()}
    assert cats["cpu"]["product_count"] == 3 and cats["cpu"]["min_price"] == 139
    page = client.get("/api/products", params={"category": "cpu", "sort": "price_asc"}).json()
    assert [p["best_price"] for p in page["items"]] == [139, 145, 299]
    assert all(not k.startswith("_") for p in page["items"] for k in p["specs"])  # internals hidden
    search = client.get("/api/products", params={"q": "7800x3d"}).json()
    assert search["total"] == 1
    am5 = client.get("/api/products", params={"category": "cpu", "spec_socket": "AM5"}).json()
    assert am5["total"] == 2
    facets = client.get("/api/products/facets", params={"category": "cpu"}).json()
    assert {f["value"] for f in facets["specs"]["socket"]} == {"AM5", "LGA1700"}
    pid = search["items"][0]["id"]
    detail = client.get(f"/api/products/{pid}").json()
    assert detail["offers"][0]["store"]["slug"] == "igeek"
    history = client.get(f"/api/products/{pid}/history").json()
    assert history["series"][0]["points"]


def test_wishlist_target_notification_flow(client, catalog):
    headers = register(client, "omar")
    gpu = client.get("/api/products", params={"q": "rtx 5060"}).json()["items"][0]
    # target above the current price -> already reached -> immediate notification
    resp = client.post("/api/wishlist", json={"product_id": gpu["id"], "target_price": 500}, headers=headers)
    assert resp.status_code == 201 and resp.json()["target_reached"] is True
    assert client.get("/api/notifications/unread-count", headers=headers).json()["unread"] == 1
    note = client.get("/api/notifications", headers=headers).json()[0]
    assert note["kind"] == "target_reached" and note["link"] == f"/product/{gpu['id']}"
    item_id = resp.json()["id"]
    patched = client.patch(f"/api/wishlist/{item_id}", json={"target_price": 300}, headers=headers).json()
    assert patched["target_price"] == 300 and patched["target_reached"] is False
    client.post("/api/notifications/read-all", headers=headers)
    assert client.get("/api/notifications/unread-count", headers=headers).json()["unread"] == 0
    assert client.delete(f"/api/wishlist/{item_id}", headers=headers).status_code == 204
    assert client.get("/api/wishlist", headers=headers).json() == []


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "purple").save(buf, "PNG")
    return buf.getvalue()


def test_marketplace_listing_lifecycle(client, catalog):
    seller = register(client, "hamza")
    buyer = register(client, "noor")
    body = {"title": "Used RTX 3060 12GB", "description": "Works great", "category": "gpu",
            "condition": "good", "price": 160, "city": "Irbid"}
    created = client.post("/api/listings", json=body, headers=seller)
    assert created.status_code == 201
    lid = created.json()["id"]

    up = client.post(f"/api/listings/{lid}/images", files={"file": ("a.png", _png(), "image/png")}, headers=seller)
    assert up.status_code == 201 and up.json()["images"][0]["url"].endswith(".webp")
    bad = client.post(f"/api/listings/{lid}/images", files={"file": ("x.png", b"not an image", "image/png")}, headers=seller)
    assert bad.status_code == 400

    anon = client.get(f"/api/listings/{lid}").json()
    assert anon["seller_contact"] is None  # contact only for logged-in users
    assert client.get(f"/api/listings/{lid}", headers=buyer).json()["seller_contact"]["email"] == "hamza@example.com"

    assert client.patch(f"/api/listings/{lid}", json={"price": 1}, headers=buyer).status_code == 403
    assert client.patch(f"/api/listings/{lid}", json={"status": "sold"}, headers=seller).json()["status"] == "sold"
    assert client.get("/api/listings").json()["total"] == 0  # sold ads leave the main list
    profile = client.get("/api/users/hamza").json()
    assert profile["sold_listings"] == 1
    assert client.post("/api/listings", json={**body, "city": "Paris"}, headers=seller).status_code == 422


def test_builder_check_and_recommend(client, catalog):
    ids = {p["name"]: p["id"] for p in client.get("/api/products", params={"page_size": 60}).json()["items"]}
    intel = next(v for k, v in ids.items() if "14400F" in k)
    am5_board = next(v for k, v in ids.items() if "B650M" in k)
    report = client.post("/api/builds/check", json={"product_ids": [intel, am5_board]}).json()
    assert report["compatible"] is False
    assert any("socket" in i["message"] for i in report["issues"])

    rec = client.post("/api/builds/recommend", json={"budget": 2000, "use_case": "gaming"}).json()
    cats = {p["category"] for p in rec["parts"]}
    assert {"cpu", "gpu", "motherboard", "ram", "storage", "psu", "case", "cooler"} <= cats
    assert rec["compatible"] is True and rec["total_price"] <= 2000


def test_chat_offline_mode(client, catalog):
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "gaming pc for 2000 JD"}]}).json()
    assert resp["mode"] == "offline" and resp["build"] is not None
    assert "[[product:" in resp["reply"] and resp["products"]
    ask = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hello"}]}).json()
    assert "budget" in ask["reply"].lower()


def test_admin_requires_admin(client):
    headers = register(client, "regular")
    assert client.get("/api/admin/stats", headers=headers).status_code == 403
