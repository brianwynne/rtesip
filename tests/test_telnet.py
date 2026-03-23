"""Tests for telnet output parsing in PjsuaTelnet."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.sip.telnet_client import PjsuaTelnet, CallState


@pytest.fixture()
def telnet(monkeypatch):
    """Create a PjsuaTelnet instance (not connected) for parsing tests.

    Replaces _emit_sync with a synchronous recorder and patches
    asyncio.create_task so tests don't need a running event loop.
    """
    # Patch asyncio.create_task in the telnet module to just consume the coroutine
    import src.sip.telnet_client as telnet_mod

    def _fake_create_task(coro, **kwargs):
        """Close the coroutine to avoid 'was never awaited' warnings."""
        coro.close()

    monkeypatch.setattr(telnet_mod.asyncio, "create_task", _fake_create_task)

    t = PjsuaTelnet()
    t._recorded_events: list[tuple[str, dict]] = []

    def _record_emit(event: str, data: dict) -> None:
        t._recorded_events.append((event, data))

    # Override _emit_sync to avoid asyncio.create_task (belt and suspenders)
    t._emit_sync = _record_emit
    return t


def _get_events(telnet: PjsuaTelnet) -> list[tuple[str, dict]]:
    """Collect all (event_type, data) tuples from the recorder."""
    return telnet._recorded_events


# --- Call state transitions ---

def test_calling_state(telnet):
    """CALLING line sets call_state and emits 'calling' event."""
    telnet.current_contact = "alice@example.com"
    telnet._parse_output("Call 0 state changed to CALLING\n")
    assert telnet.call_state == CallState.CALLING

    events = _get_events(telnet)
    assert any(e[0] == "calling" for e in events)


def test_ringing_state(telnet):
    """180 Ringing sets state to RINGING."""
    telnet.current_contact = "alice@example.com"
    telnet._parse_output("Call 0 state changed to EARLY (180 Ringing)\n")
    assert telnet.call_state == CallState.RINGING

    events = _get_events(telnet)
    assert any(e[0] == "ringing" for e in events)


def test_confirmed_via_call_list(telnet):
    """CONFIRMED in call list output sets state to CONNECTED."""
    telnet._parse_output("Current call id=0 to sip:alice@example.com [CONFIRMED]\n")
    assert telnet.call_state == CallState.CONNECTED

    events = _get_events(telnet)
    assert any(e[0] == "connected" for e in events)


def test_disconnected_state(telnet):
    """DISCONNCTD line resets state to IDLE and emits 'ended'."""
    telnet.call_state = CallState.CONNECTED
    telnet.current_contact = "alice@example.com"
    telnet._parse_output("[DISCONNCTD] t: sip:alice@example.com;tag=abc123\n")
    assert telnet.call_state == CallState.IDLE
    assert telnet.current_contact is None

    events = _get_events(telnet)
    assert any(e[0] == "ended" for e in events)
    ended = next(e for e in events if e[0] == "ended")
    assert "sip:alice@example.com" in ended[1]["destination"]


# --- Registration status ---

def test_registration_200(telnet):
    """Successful registration (200) sets account registered and sip_ready."""
    telnet._parse_output(
        "[ 0] sip:alice@example.com: 200/OK (expires=600)\n"
    )
    assert telnet.active_accounts.get("alice@example.com") is True
    assert telnet.sip_ready is True

    events = _get_events(telnet)
    acct_events = [e for e in events if e[0] == "account"]
    assert len(acct_events) >= 1
    assert acct_events[0][1]["status"] == 200
    assert acct_events[0][1]["registered"] is True


def test_registration_403(telnet):
    """Failed registration (403) marks account as not registered."""
    telnet._parse_output(
        "[ 0] sip:alice@example.com: 403/Forbidden (expires=-1)\n"
    )
    assert telnet.active_accounts.get("alice@example.com") is False

    events = _get_events(telnet)
    acct_events = [e for e in events if e[0] == "account"]
    assert acct_events[0][1]["status"] == 403
    assert acct_events[0][1]["registered"] is False


def test_registration_status_format2(telnet):
    """Alternate registration status format is also parsed."""
    telnet._parse_output(
        "sip:bob@sip.test.com: registration success, status=200 (OK)\n"
    )
    assert telnet.active_accounts.get("bob@sip.test.com") is True


# --- Incoming call ---

def test_incoming_call_from_header(telnet):
    """From: header triggers incoming state with parsed contact."""
    telnet._parse_output('From: "Bob Smith" <sip:bob@example.com>\n')
    assert telnet.call_state == CallState.INCOMING
    assert "bob@example.com" in telnet.current_contact

    events = _get_events(telnet)
    assert any(e[0] == "incoming" for e in events)


def test_incoming_call_list_format(telnet):
    """INCOMING in call list also triggers incoming state."""
    telnet._parse_output("Current call id=0 to sip:bob@example.com [INCOMING]\n")
    assert telnet.call_state == CallState.INCOMING


# --- Error detection ---

def test_stun_timeout_error(telnet):
    """STUN timeout emits network_error event."""
    telnet._parse_output("PJNATH_ESTUNTIMEDOUT: STUN transaction has timed out\n")

    events = _get_events(telnet)
    assert any(e[0] == "network_error" for e in events)


def test_stun_send_error(telnet):
    """Error sending STUN request emits network_error."""
    telnet._parse_output("Error sending STUN request: Network unreachable\n")

    events = _get_events(telnet)
    assert any(e[0] == "network_error" for e in events)


def test_stun_error_suppressed_when_nominated(telnet):
    """STUN error with 'not nominated' is ignored (ICE negotiation noise)."""
    telnet._parse_output("PJNATH_ESTUNTIMEDOUT: not nominated pair\n")

    events = _get_events(telnet)
    assert not any(e[0] == "network_error" for e in events)


def test_audio_device_error(telnet):
    """ALSA device error emits audio_error."""
    telnet._parse_output("PJMEDIA_EAUD_SYSERR: Audio subsystem error\n")

    events = _get_events(telnet)
    assert any(e[0] == "audio_error" for e in events)


def test_sip_reason_code(telnet):
    """SIP reason line emits reason event with code and text."""
    telnet._parse_output("[reason=486 (Busy Here)]\n")

    events = _get_events(telnet)
    reason_events = [e for e in events if e[0] == "reason"]
    assert len(reason_events) == 1
    assert reason_events[0][1]["code"] == 486
    assert reason_events[0][1]["verbose"] == "Busy Here"


def test_connection_error_when_idle(telnet):
    """Connection timeout while idle emits connection_error."""
    telnet.current_contact = None
    telnet._parse_output("Connection timed out\n")

    events = _get_events(telnet)
    assert any(e[0] == "connection_error" for e in events)


def test_connection_error_suppressed_during_call(telnet):
    """Connection timeout during active call is not emitted as connection_error."""
    telnet.current_contact = "alice@example.com"
    telnet._parse_output("Connection timed out\n")

    events = _get_events(telnet)
    assert not any(e[0] == "connection_error" for e in events)


# --- Contact resolution ---

def test_resolve_contact_display_name(telnet):
    """_resolve_contact parses display name from SIP From header."""
    result = telnet._resolve_contact('"Alice Smith" <sip:alice@example.com>')
    assert "Alice Smith" in result
    assert "alice@example.com" in result


def test_resolve_contact_no_display_name(telnet):
    """_resolve_contact returns bare address when no display name."""
    result = telnet._resolve_contact("<sip:alice@example.com>")
    assert result == "alice@example.com"


def test_resolve_contact_pstn_strips_domain(telnet):
    """_resolve_contact strips domain from PSTN-style addresses."""
    result = telnet._resolve_contact("<sip:+353861234567@gateway.example.com>")
    assert "+353861234567" in result
    assert "gateway.example.com" not in result


def test_resolve_contact_lookup_from_file(telnet, tmp_data_dir):
    """_resolve_contact uses contacts.json for name lookup."""
    import json
    contacts_file = tmp_data_dir / "contacts.json"
    contacts_file.write_text(json.dumps([
        {"name": "Studio A", "address": "studio-a@example.com"}
    ]))

    result = telnet._resolve_contact("<sip:studio-a@example.com>")
    assert "Studio A" in result


# --- Empty / junk input ---

def test_empty_lines_ignored(telnet):
    """Empty lines and prompt lines produce no events."""
    telnet._parse_output("\n\n  \nrtesip>\n")
    events = _get_events(telnet)
    assert len(events) == 0
