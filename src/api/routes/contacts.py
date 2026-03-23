"""Contacts / speed dial management."""

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import require_api_key
from src.config.settings import DATA_DIR

router = APIRouter(dependencies=[Depends(require_api_key)])

CONTACTS_FILE = DATA_DIR / "contacts.json"


def _load_contacts() -> list[dict]:
    if CONTACTS_FILE.exists():
        return json.loads(CONTACTS_FILE.read_text())
    return []


def _save_contacts(contacts: list[dict]) -> None:
    CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CONTACTS_FILE.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(contacts, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, CONTACTS_FILE)


@router.get("/")
async def list_contacts():
    return _load_contacts()


@router.post("/")
async def add_contact(contact: dict):
    contacts = _load_contacts()
    contact["id"] = max((c.get("id", 0) for c in contacts), default=0) + 1
    contacts.append(contact)
    _save_contacts(contacts)
    return contact


@router.put("/{contact_id}")
async def update_contact(contact_id: int, contact: dict):
    contacts = _load_contacts()
    for i, c in enumerate(contacts):
        if c.get("id") == contact_id:
            contact["id"] = contact_id
            contacts[i] = contact
            _save_contacts(contacts)
            return contact
    raise HTTPException(status_code=404, detail="Contact not found")


@router.delete("/{contact_id}")
async def delete_contact(contact_id: int):
    contacts = _load_contacts()
    contacts = [c for c in contacts if c.get("id") != contact_id]
    _save_contacts(contacts)
    return {"deleted": contact_id}
