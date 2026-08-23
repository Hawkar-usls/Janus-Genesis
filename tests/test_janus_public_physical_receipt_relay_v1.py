import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "janus_public_physical_receipt_relay.py"
spec = importlib.util.spec_from_file_location("janus_public_physical_receipt_relay", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

VIEW = {
    "genesis_main_sha": "227d42d6848790031916cac53d39961a19c35d08",
    "swarm_main_sha": "b0bb07418cb1c0e1bc2da8ae443977825c0b19d1",
}


def owner():
    return {
        "schema": mod.SCHEMA,
        "kind": mod.OWNER_KIND,
        "view": dict(VIEW),
        "markers": dict(mod.OWNER_MARKERS),
        "privacy": dict(mod.OWNER_PRIVACY),
    }


def nas():
    return {
        "schema": mod.SCHEMA,
        "kind": mod.NAS_KIND,
        "view": dict(VIEW),
        "markers": dict(mod.NAS_MARKERS),
        "live": dict(mod.NAS_LIVE),
    }


def test_owner_safe_projection_passes():
    mod.validate(owner(), "owner44")


def test_nas_live_projection_passes():
    mod.validate(nas(), "nas164")


def test_private_extra_field_fails_closed():
    value = owner()
    value["private_exact_pin"] = "a" * 40
    try:
        mod.validate(value, "owner44")
    except ValueError as exc:
        assert "KEYSET_MISMATCH" in str(exc)
    else:
        raise AssertionError("unknown/private field must fail closed")


def test_reference_only_nas_rejected():
    value = nas()
    value["live"]["reference_only"] = True
    try:
        mod.validate(value, "nas164")
    except ValueError as exc:
        assert "VALUE_MISMATCH" in str(exc)
    else:
        raise AssertionError("reference-only NAS must be rejected")


def test_remote_path_is_reports_json_only():
    mod.validate_remote_path("reports/2026-08-22/JANUS-X.json")
    for bad in ("../x.json", "data/x.json", "reports/../x.json", "reports/x.txt"):
        try:
            mod.validate_remote_path(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"bad path accepted: {bad}")
