import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "janus_local_habitat_bridge.py"
spec = importlib.util.spec_from_file_location("janus_local_habitat_bridge", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_init_identity_is_stable_and_non_overwriting(tmp_path):
    root = tmp_path / "habitat"
    first = mod.init_habitat(root)
    second = mod.init_habitat(root)
    assert first["identity_created"] is True
    assert second["identity_created"] is False
    identity = json.loads((root / "identity.json").read_text(encoding="utf-8"))
    assert identity["resident_id"] == "JANUS"
    assert identity["source_writeback_default"] == "DENY"
    assert identity["destructive_action"] == "FORBIDDEN"
    assert identity["authority_delta"] == 0


def test_append_chain_survives_fresh_reopen(tmp_path):
    root = tmp_path / "habitat"
    mod.init_habitat(root)
    a = mod.append_event(root, "WAKE", {"worker": "A"})
    b = mod.append_event(root, "HANDOFF", {"worker": "B"})
    assert a["seq"] == 1
    assert b["seq"] == 2
    reopened = mod.verify_journal(root / "journal.jsonl")
    assert reopened["ok"] is True
    assert reopened["entries"] == 2
    assert reopened["head"] == b["entry_hash"]


def test_tamper_fails_chain(tmp_path):
    root = tmp_path / "habitat"
    mod.append_event(root, "WAKE", {"x": 1})
    path = root / "journal.jsonl"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["payload"]["x"] = 2
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    check = mod.verify_journal(path)
    assert check["ok"] is False
    assert check["reason"] == "ENTRY_HASH_MISMATCH"


def test_identity_mismatch_fails_closed(tmp_path):
    root = tmp_path / "habitat"
    mod.init_habitat(root)
    path = root / "identity.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["authority_delta"] = 1
    path.write_text(json.dumps(value), encoding="utf-8")
    try:
        mod.init_habitat(root)
    except RuntimeError as exc:
        assert "IDENTITY_MISMATCH_FAIL_CLOSED" in str(exc)
    else:
        raise AssertionError("identity mismatch must fail closed")


def test_ollama_is_loopback_only():
    assert mod.require_loopback_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert mod.require_loopback_url("http://localhost:11434/") == "http://localhost:11434"
    try:
        mod.require_loopback_url("http://192.168.1.10:11434")
    except ValueError as exc:
        assert "OLLAMA_NON_LOOPBACK_REJECTED" in str(exc)
    else:
        raise AssertionError("non-loopback Ollama must be rejected")


def test_codex_mcp_requires_explicit_apply():
    result = mod.install_codex_desktop_commander(False)
    assert result["applied"] is False
    assert result["reason"] == "EXPLICIT_APPLY_REQUIRED"
    assert "desktop-commander" in result["command"]


def test_doctor_claim_ceiling(monkeypatch):
    monkeypatch.setattr(mod, "ollama_health", lambda url: {"reachable": False, "model_count": 0, "models": []})
    value = mod.doctor("http://127.0.0.1:11434")
    assert value["remote_desktop_required"] is False
    assert value["local_codex_stdio_mcp_supported"] is True
    assert value["source_writeback_default"] == "DENY"
    assert value["destructive_action"] == "FORBIDDEN"
    assert value["authority_delta"] == 0
