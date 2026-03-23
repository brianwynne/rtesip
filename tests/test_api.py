"""Tests for REST API endpoints."""

import pytest


# --- System ---

def test_system_status(client):
    """GET /api/system/status returns expected fields."""
    resp = client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu_temp" in data
    assert "uptime_seconds" in data
    assert "hostname" in data
    assert "serial" in data
    assert "model" in data


def test_system_config(client):
    """GET /api/system/config returns full config with all sections."""
    resp = client.get("/api/system/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "sip" in data
    assert "audio" in data
    assert "base" in data


# --- SIP ---

def test_sip_settings_defaults(client):
    """GET /api/sip/settings returns default SIP config."""
    resp = client.get("/api/sip/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["transport"] == "tls"
    assert data["username"] == ""
    assert data["reg_timeout"] == 600
    assert "codecs" in data


def test_sip_settings_update(client):
    """PUT /api/sip/settings updates values and returns them."""
    resp = client.put("/api/sip/settings", json={
        "username": "alice",
        "registrar": "sip.example.com",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"
    assert data["registrar"] == "sip.example.com"
    # Defaults preserved
    assert data["transport"] == "tls"

    # Verify persisted
    resp2 = client.get("/api/sip/settings")
    assert resp2.json()["username"] == "alice"


def test_sip_status(client):
    """GET /api/sip/status returns running state."""
    resp = client.get("/api/sip/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "pid" in data


# --- Contacts ---

def test_contacts_empty_initially(client):
    """GET /api/contacts/ returns empty list when no contacts exist."""
    resp = client.get("/api/contacts/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_contacts_create(client):
    """POST /api/contacts/ creates a contact with an auto-assigned id."""
    resp = client.post("/api/contacts/", json={
        "name": "Alice",
        "address": "alice@sip.example.com",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice"
    assert data["id"] == 1

    # Verify it shows in the list
    resp2 = client.get("/api/contacts/")
    assert len(resp2.json()) == 1


def test_contacts_create_multiple(client):
    """Creating multiple contacts gives incrementing ids."""
    client.post("/api/contacts/", json={"name": "Alice", "address": "alice@example.com"})
    resp = client.post("/api/contacts/", json={"name": "Bob", "address": "bob@example.com"})
    assert resp.json()["id"] == 2

    resp2 = client.get("/api/contacts/")
    assert len(resp2.json()) == 2


def test_contacts_delete(client):
    """DELETE /api/contacts/{id} removes the contact."""
    resp = client.post("/api/contacts/", json={"name": "Alice", "address": "alice@example.com"})
    cid = resp.json()["id"]

    del_resp = client.delete(f"/api/contacts/{cid}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == cid

    # Verify gone
    resp2 = client.get("/api/contacts/")
    assert len(resp2.json()) == 0


def test_contacts_update(client):
    """PUT /api/contacts/{id} updates an existing contact."""
    resp = client.post("/api/contacts/", json={"name": "Alice", "address": "alice@example.com"})
    cid = resp.json()["id"]

    up_resp = client.put(f"/api/contacts/{cid}", json={"name": "Alice B", "address": "alice-b@example.com"})
    assert up_resp.status_code == 200
    assert up_resp.json()["name"] == "Alice B"
    assert up_resp.json()["id"] == cid


def test_contacts_update_not_found(client):
    """PUT /api/contacts/{id} returns 404 for unknown id."""
    resp = client.put("/api/contacts/999", json={"name": "Ghost"})
    assert resp.status_code == 404


# --- Audio ---

def test_audio_settings_defaults(client):
    """GET /api/audio/settings returns default audio config."""
    resp = client.get("/api/audio/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["channels"] == 1
    assert data["bitrate"] == 72000
    assert data["input"] == "USB"
    assert data["auto_answer"] is False


# --- Update ---

def test_update_version(client):
    """GET /api/update/version returns version info."""
    resp = client.get("/api/update/version")
    assert resp.status_code == 200
    data = resp.json()
    assert "version" in data
    assert "partition" in data
