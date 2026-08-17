from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS_PATH = ROOT / ".cert" / "goldprompt-v2-cross-repo-inputs.json"
OUT = ROOT / ".cert" / "out"
DEMI_TOOLS = ROOT / "_cert" / "demihead" / "tools"
GENESIS_TOOLS = ROOT / "tools"


def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(value):
    return hashlib.sha256(canon(value)).hexdigest()


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_exact_subject(name, value, mode):
    OUT.mkdir(parents=True, exist_ok=True)
    if mode == "js-pretty":
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    elif mode == "python-sorted-line":
        text = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
    else:
        raise ValueError("UNKNOWN_SUBJECT_SERIALIZATION")
    (OUT / name).write_text(text, encoding="utf-8")


def verify_envelope(envelope):
    payload = dict(envelope)
    claimed = payload.pop("envelope_sha256")
    if sha256(payload) != claimed:
        raise ValueError(f"ENVELOPE_SHA_MISMATCH:{envelope.get('face_id')}")
    packet = envelope["packet"]
    if packet["source"]["source_revision"] != envelope["source_revision"]:
        raise ValueError(f"ENVELOPE_PACKET_REVISION_MISMATCH:{envelope.get('face_id')}")
    if packet["goldprompt_receipt"]["face_id"] != envelope["face_id"]:
        raise ValueError(f"ENVELOPE_FACE_MISMATCH:{envelope.get('face_id')}")
    return packet


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    inputs = json.loads(INPUTS_PATH.read_text(encoding="utf-8"))
    expected = inputs["expected_revisions"]
    left = verify_envelope(inputs["hrain_envelope"])
    right = verify_envelope(inputs["inaihr_envelope"])
    demi_receipt = inputs["demihead_receipt"]
    genesis_receipt = inputs["genesis_receipt"]

    os.environ["JANUS_SOURCE_REVISION"] = expected["DEMIHEAD_ARBITER"]
    sys.path.insert(0, str(DEMI_TOOLS))
    import hemisphere_bridge as demi_bridge  # type: ignore

    demi_result = demi_bridge.combine_packets(left=left, right=right)
    if demi_result["goldprompt_receipt"] != demi_receipt:
        raise ValueError("DEMIHEAD_RUNTIME_RECEIPT_ARTIFACT_MISMATCH")
    if not demi_bridge.verify_receipt_chain_result(demi_result):
        raise ValueError("DEMIHEAD_RECEIPT_CHAIN_REPLAY_FAILED")

    sys.path = [p for p in sys.path if p != str(DEMI_TOOLS)]
    for name in ("goldprompt_handshake", "hemisphere_bridge"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(GENESIS_TOOLS))
    import goldprompt_face_receipts_v2 as gp  # type: ignore
    from goldprompt_face_bundle_verifier_v2 import verify_bundle_with_raw_evidence, verify_compact_bundle_replay  # type: ignore

    receipts = [left["goldprompt_receipt"], right["goldprompt_receipt"], demi_receipt, genesis_receipt]
    bundle = gp.collect_bundle(
        receipts,
        left_packet=left,
        right_packet=right,
        demihead_result=demi_result,
        expected_revisions=expected,
    )
    if not verify_compact_bundle_replay(bundle):
        raise ValueError("GENESIS_COMPACT_BUNDLE_REPLAY_FAILED")
    raw_cert = verify_bundle_with_raw_evidence(
        bundle,
        left_packet=left,
        right_packet=right,
        demihead_result=demi_result,
        expected_revisions=expected,
    )

    write_exact_subject("left-hrain-receipt.json", left["goldprompt_receipt"], "js-pretty")
    write_exact_subject("right-inaihr-receipt.json", right["goldprompt_receipt"], "js-pretty")
    write_exact_subject("demihead-receipt.json", demi_receipt, "python-sorted-line")
    write_exact_subject("genesis-receipt.json", genesis_receipt, "python-sorted-line")

    expected_subject_hashes = {
        "left-hrain-receipt.json": "2b0b836e01fe87fe04c4cf23a92e337a6b6ab182dcef9e5fc84ff9baad04ecd3",
        "right-inaihr-receipt.json": "cfab3bdc35d860f84c1c67fc68b2a82f4a8235d68484fa6b086ce6ef6a3e55f9",
        "demihead-receipt.json": "bbb9ed67145b9a0d9dca07fb487f3c718b863d5a5f7446d43ccd50863bbcfa83",
        "genesis-receipt.json": "a4a5deb55023763c9a60958ff13062122b02de4be4e1accbd1f88de8d0289b51",
    }
    for name, expected_hash in expected_subject_hashes.items():
        actual = file_sha256(OUT / name)
        if actual != expected_hash:
            raise ValueError(f"ATTESTATION_SUBJECT_BYTE_RECONSTRUCTION_MISMATCH:{name}:{actual}")

    write("actual-left-envelope.json", inputs["hrain_envelope"])
    write("actual-right-envelope.json", inputs["inaihr_envelope"])
    write("demihead-result-from-actual-packets.json", demi_result)
    write("goldprompt-four-face-bundle-v2.json", bundle)
    write("goldprompt-raw-replay-certificate-v2.json", raw_cert)

    summary = {
        "schema": "janus.goldprompt.cross_repo_raw_replay_pre_attestation.v2",
        "proof_mode": "OFFLINE_CROSS_REPOSITORY_RAW_EVIDENCE_REPLAY",
        "expected_revisions": expected,
        "dependency_manifest_digest_sha256": gp.EXPECTED_DEPENDENCY_MANIFEST_DIGEST,
        "left_packet_sha256": gp.sha256(left),
        "right_packet_sha256": gp.sha256(right),
        "demihead_chain_sha256": demi_result["receipt_chain"]["chain_sha256"],
        "bundle_sha256": bundle["bundle_sha256"],
        "attestation_subject_file_sha256s": expected_subject_hashes,
        "raw_replay_certificate": raw_cert,
        "end_to_end_receipt_binding_established": True,
        "artifact_origin_attestation_pending_external_verify": True,
        "live_process_identity_established": False,
        "end_to_end_message_authentication_established": False,
        "authority_delta": 0,
    }
    write("pre-attestation-summary.json", summary)
    print("OFFLINE_CROSS_REPOSITORY_RAW_EVIDENCE_REPLAY=PASS")
    print("BUNDLE_SHA256=" + bundle["bundle_sha256"])
    print("CHAIN_SHA256=" + demi_result["receipt_chain"]["chain_sha256"])


if __name__ == "__main__":
    main()
