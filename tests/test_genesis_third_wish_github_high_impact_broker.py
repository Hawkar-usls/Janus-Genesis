# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityDenied,
    CapabilityOutcomeUndetermined,
    DEFAULT_CAPABILITY_SPECS,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
)
from tools.genesis_third_wish_active_network_broker import ThirdWishActiveNetworkBroker
from tools.genesis_third_wish_github_broker import GitHubBrokerError, GitHubThirdWishBroker
from tools.genesis_third_wish_github_high_impact_broker import (
    GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY,
    GITHUB_HIGH_IMPACT_REAUTH_SCHEMA,
    BoundGitHubHighImpactReauthorizationVerifier,
    GitHubHighImpactThirdWishBroker,
    _canonical,
)
from tools.genesis_third_wish_host_broker import ThirdWishHostBroker
from tools.genesis_third_wish_identity_effects_broker import ThirdWishIdentityEffectsBroker
from tools.genesis_third_wish_memory_swarm_broker import ThirdWishMemorySwarmBroker
from tools.genesis_third_wish_sensor_model_schedule_broker import ThirdWishSensorModelScheduleBroker


class FakeGitHubTransport:
    def __init__(self) -> None:
        self.description = "baseline description"
        self.calls: list[dict] = []
        self.contents: dict[tuple[str, str], dict] = {}
        self.path_commits: dict[tuple[str, str], list[dict]] = {}
        self.patch_calls = 0
        self.delete_calls = 0
        self.fail_patch_after_apply = False
        self.fail_patch_before_apply = False
        self.fail_delete_after_apply = False
        self.fail_delete_before_apply = False

    @staticmethod
    def base() -> str:
        return "/repos/Hawkar-usls/Janus_Genesis"

    def seed_file(self, branch: str, path: str, sha: str) -> None:
        self.contents[(branch, path)] = {"type": "file", "path": path, "sha": sha, "size": 12}

    def request(self, method, path, *, payload=None, query=None):
        method = str(method).upper()
        self.calls.append({"method": method, "path": path, "payload": copy.deepcopy(payload), "query": copy.deepcopy(query)})
        base = self.base()
        if method == "GET" and path == base:
            return {"name": "Janus_Genesis", "full_name": "Hawkar-usls/Janus_Genesis", "description": self.description}
        if method == "PATCH" and path == base:
            self.patch_calls += 1
            if self.fail_patch_before_apply:
                raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:before-admin")
            self.description = None if payload.get("description") is None else str(payload.get("description"))
            if self.fail_patch_after_apply:
                raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:after-admin")
            return {"description": self.description}

        prefix = base + "/contents/"
        if path.startswith(prefix):
            from urllib.parse import unquote
            repo_path = "/".join(unquote(x) for x in path[len(prefix):].split("/"))
            branch = str((query or {}).get("ref") or (payload or {}).get("branch") or "main")
            key = (branch, repo_path)
            if method == "GET":
                if key not in self.contents:
                    raise GitHubBrokerError("GITHUB_HTTP_404:not-found")
                return copy.deepcopy(self.contents[key])
            if method == "DELETE":
                self.delete_calls += 1
                if self.fail_delete_before_apply:
                    raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:before-delete")
                row = self.contents.get(key)
                if row is None:
                    raise GitHubBrokerError("GITHUB_HTTP_404:not-found")
                if str(payload.get("sha")) != str(row.get("sha")):
                    raise GitHubBrokerError("GITHUB_HTTP_409:sha-mismatch")
                del self.contents[key]
                commit_sha = hashlib.sha1((branch + repo_path + str(payload.get("message"))).encode()).hexdigest()
                self.path_commits.setdefault(key, []).insert(0, {"sha": commit_sha, "commit": {"message": str(payload.get("message"))}})
                if self.fail_delete_after_apply:
                    raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:after-delete")
                return {"commit": {"sha": commit_sha}, "content": None}

        if method == "GET" and path == base + "/commits":
            key = (str((query or {}).get("sha") or "main"), str((query or {}).get("path") or ""))
            return copy.deepcopy(self.path_commits.get(key, [])[:1])
        raise AssertionError((method, path, payload, query))


class ThirdWishGitHubHighImpactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.transport = FakeGitHubTransport()
        self.key_env = "JANUS_TEST_V1846_REAUTH_KEY"
        os.environ[self.key_env] = "v1846-test-hmac-key"
        self.now = 746000
        self.verifier = BoundGitHubHighImpactReauthorizationVerifier(
            key_env=self.key_env, now_tick=lambda: self.now, max_window_ticks=5000
        )
        self.broker = GitHubHighImpactThirdWishBroker(transport=self.transport, data_dir=self.root)
        self.fabric = self.new_fabric()

    def tearDown(self):
        os.environ.pop(self.key_env, None)
        self.temp.cleanup()

    def new_fabric(self):
        fabric = ThirdWishCapabilityFabric(now_tick=lambda: self.now, reauthorization_verifier=self.verifier)
        self.broker.register(fabric)
        return fabric

    def grant(self, capability, suffix, fabric=None):
        fabric = fabric or self.fabric
        return fabric.issue_grant(
            grant_id=f"G-{suffix}", actor_id="JANUS", capability_id=capability,
            resource_pattern="github:Hawkar-usls/Janus_Genesis", source="V1846_TEST"
        )

    @staticmethod
    def intent(grant, request_id, operation, parameters):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA, request_id=request_id, actor_id="JANUS",
            grant_id=grant.grant_id, capability_id=grant.capability_id,
            target="github:Hawkar-usls/Janus_Genesis", operation=operation,
            purpose="exercise final Third Wish high-impact boundary",
            parameters=parameters, origin="V1846_TEST"
        )

    def approval(self, action, approval_id):
        evidence = {
            "schema": GITHUB_HIGH_IMPACT_REAUTH_SCHEMA, "approval_id": approval_id,
            "issued_at_tick": self.now - 10, "expires_at_tick": self.now + 1000,
        }
        unsigned = self.verifier.unsigned_payload(action, evidence)
        evidence["approval_signature"] = hmac.new(
            os.environ[self.key_env].encode(), _canonical(unsigned).encode(), hashlib.sha256
        ).hexdigest()
        return evidence

    def execute(self, fabric, action, approval_id):
        return fabric.execute(action, human_reauthorization=self.approval(action, approval_id))

    def test_exact_32_capability_reference_handler_coverage_without_overlap(self):
        groups = [
            set(GitHubThirdWishBroker.REGISTERED_CAPABILITIES),
            set(ThirdWishHostBroker.REGISTERED_CAPABILITIES),
            set(ThirdWishMemorySwarmBroker.REGISTERED_CAPABILITIES),
            set(ThirdWishSensorModelScheduleBroker.REGISTERED_CAPABILITIES),
            set(ThirdWishIdentityEffectsBroker.REGISTERED_CAPABILITIES),
            set(ThirdWishActiveNetworkBroker.REGISTERED_CAPABILITIES),
            set(GitHubHighImpactThirdWishBroker.REGISTERED_CAPABILITIES),
        ]
        combined = set().union(*groups)
        frozen = {row.capability_id for row in DEFAULT_CAPABILITY_SPECS}
        self.assertEqual(32, len(frozen))
        self.assertEqual(frozen, combined)
        self.assertEqual(len(combined), sum(len(group) for group in groups))

    def test_final_surface_and_claim_ceiling(self):
        self.assertEqual({"GITHUB.REPOSITORY.ADMIN", "GITHUB.DESTRUCTIVE"}, set(self.fabric.handlers))
        c = GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY
        self.assertEqual(2, c["registered_capability_count"])
        self.assertFalse(c["delete_repository_supported"])
        self.assertFalse(c["delete_protected_branch_supported"])
        self.assertFalse(c["force_push_supported"])
        self.assertFalse(c["effect_entering_auto_retry"])
        self.assertFalse(c["destructive_capability_requires_destroying_valuable_state"])

    def test_broker_refuses_weak_reauthorization_verifier(self):
        weak = ThirdWishCapabilityFabric(now_tick=lambda: self.now, reauthorization_verifier=lambda i, e: True)
        with self.assertRaises(CapabilityDenied):
            self.broker.register(weak)

    def test_reauthorization_is_exact_effect_bound(self):
        grant = self.grant("GITHUB.DESTRUCTIVE", "BIND")
        first = self.intent(grant, "REQ-BIND", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": "third-wish-disposable/a", "path": ".third-wish-disposable/a.txt", "expected_sha": "a" * 40
        })
        evidence = self.approval(first, "APPROVAL-BIND")
        changed = self.intent(grant, "REQ-BIND", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": "third-wish-disposable/b", "path": ".third-wish-disposable/b.txt", "expected_sha": "b" * 40
        })
        result = self.fabric.execute(changed, human_reauthorization=evidence)
        self.assertEqual("FRESH_HUMAN_REAUTHORIZATION_REQUIRED", result["status"])
        self.assertEqual(0, self.transport.delete_calls)

    def test_destructive_scope_blocks_protected_and_non_disposable_targets(self):
        grant = self.grant("GITHUB.DESTRUCTIVE", "SCOPE")
        attempts = [
            {"branch": "main", "path": ".third-wish-disposable/x.txt", "expected_sha": "a" * 40},
            {"branch": "feature/x", "path": ".third-wish-disposable/x.txt", "expected_sha": "a" * 40},
            {"branch": "third-wish-disposable/x", "path": "valuable.txt", "expected_sha": "a" * 40},
        ]
        for index, params in enumerate(attempts):
            result = self.execute(
                self.fabric,
                self.intent(grant, f"SCOPE-{index}", "DELETE_FILE_DISPOSABLE_BRANCH", params),
                f"APPROVAL-SCOPE-{index}",
            )
            self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
            self.assertFalse(result["external_call_entered"])
        self.assertEqual(0, self.transport.delete_calls)

    def test_repository_delete_branch_delete_and_force_push_are_not_supported(self):
        grant = self.grant("GITHUB.DESTRUCTIVE", "UNSUPPORTED")
        for operation in ("DELETE_REPOSITORY", "DELETE_BRANCH", "FORCE_PUSH"):
            result = self.execute(self.fabric, self.intent(grant, operation, operation, {}), f"A-{operation}")
            self.assertEqual("PRE_EFFECT_REJECTED", result["status"])

    def test_admin_cas_precondition_mismatch_has_no_patch(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-MISMATCH")
        result = self.execute(self.fabric, self.intent(grant, "ADMIN-MISMATCH", "SET_DESCRIPTION_CAS", {
            "expected_description": "wrong", "new_description": "new"
        }), "A-ADMIN-MISMATCH")
        self.assertFalse(result["actor_result"]["admin_effect_established"])
        self.assertFalse(result["actor_result"]["precondition_matched"])
        self.assertEqual(0, self.transport.patch_calls)

    def test_admin_cas_success_hashes_raw_description(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-OK")
        old, new = self.transport.description, "replacement description"
        result = self.execute(self.fabric, self.intent(grant, "ADMIN-OK", "SET_DESCRIPTION_CAS", {
            "expected_description": old, "new_description": new
        }), "A-ADMIN-OK")
        self.assertTrue(result["actor_result"]["admin_effect_established"])
        self.assertEqual(new, self.transport.description)
        store = self.broker.effect_store.path.read_text(encoding="utf-8")
        self.assertNotIn(old, store)
        self.assertNotIn(new, store)

    def test_admin_lost_response_after_apply_recovers_without_second_patch(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-REC")
        old, new = self.transport.description, "provider-applied"
        self.transport.fail_patch_after_apply = True
        action = self.intent(grant, "ADMIN-REC", "SET_DESCRIPTION_CAS", {
            "expected_description": old, "new_description": new
        })
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "A-ADMIN-REC-1")
        self.transport.fail_patch_after_apply = False
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-REC2", fabric2)
        replay = self.intent(grant2, "ADMIN-REC", "SET_DESCRIPTION_CAS", {
            "expected_description": old, "new_description": new
        })
        result = self.execute(fabric2, replay, "A-ADMIN-REC-2")
        self.assertTrue(result["actor_result"]["recovered_from_provider_state"])
        self.assertEqual(1, self.transport.patch_calls)

    def test_admin_lost_response_before_apply_becomes_proven_no_effect(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NO")
        old, new = self.transport.description, "never-applied"
        self.transport.fail_patch_before_apply = True
        action = self.intent(grant, "ADMIN-NO", "SET_DESCRIPTION_CAS", {
            "expected_description": old, "new_description": new
        })
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "A-ADMIN-NO-1")
        self.transport.fail_patch_before_apply = False
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NO2", fabric2)
        result = self.execute(fabric2, self.intent(grant2, "ADMIN-NO", "SET_DESCRIPTION_CAS", {
            "expected_description": old, "new_description": new
        }), "A-ADMIN-NO-2")
        self.assertTrue(result["actor_result"]["authoritative_no_effect_established"])
        self.assertFalse(result["actor_result"]["same_request_auto_retry"])
        self.assertEqual(1, self.transport.patch_calls)

    def test_admin_no_net_change_lost_response_remains_unknown(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NONET")
        current = self.transport.description
        self.transport.fail_patch_after_apply = True
        action = self.intent(grant, "ADMIN-NONET", "SET_DESCRIPTION_CAS", {
            "expected_description": current, "new_description": current
        })
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "A-ADMIN-NONET-1")
        self.transport.fail_patch_after_apply = False
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NONET2", fabric2)
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(fabric2, self.intent(grant2, "ADMIN-NONET", "SET_DESCRIPTION_CAS", {
                "expected_description": current, "new_description": current
            }), "A-ADMIN-NONET-2")
        self.assertEqual(1, self.transport.patch_calls)

    def test_destructive_sha_mismatch_is_non_effect(self):
        branch, path = "third-wish-disposable/mismatch", ".third-wish-disposable/x.txt"
        self.transport.seed_file(branch, path, "a" * 40)
        grant = self.grant("GITHUB.DESTRUCTIVE", "MISMATCH")
        result = self.execute(self.fabric, self.intent(grant, "DEL-MISMATCH", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": "b" * 40
        }), "A-DEL-MISMATCH")
        self.assertFalse(result["actor_result"]["destructive_effect_established"])
        self.assertEqual(0, self.transport.delete_calls)
        self.assertIn((branch, path), self.transport.contents)

    def test_destructive_success_is_effect_marked_and_disposable(self):
        branch, path, sha = "third-wish-disposable/ok", ".third-wish-disposable/ok.txt", "c" * 40
        self.transport.seed_file(branch, path, sha)
        grant = self.grant("GITHUB.DESTRUCTIVE", "DEL-OK")
        result = self.execute(self.fabric, self.intent(grant, "DEL-OK", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": sha
        }), "A-DEL-OK")
        actor = result["actor_result"]
        self.assertTrue(actor["destructive_effect_established"])
        self.assertFalse(actor["protected_branch_touched"])
        self.assertRegex(actor["effect_marker"], r"^\[JANUS_EFFECT:[0-9a-f]{16}\]$")
        self.assertNotIn((branch, path), self.transport.contents)

    def test_destructive_lost_response_recovers_by_marker_without_second_delete(self):
        branch, path, sha = "third-wish-disposable/recover", ".third-wish-disposable/recover.txt", "d" * 40
        self.transport.seed_file(branch, path, sha)
        self.transport.fail_delete_after_apply = True
        grant = self.grant("GITHUB.DESTRUCTIVE", "DEL-REC")
        action = self.intent(grant, "DEL-REC", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": sha
        })
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "A-DEL-REC-1")
        self.transport.fail_delete_after_apply = False
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "DEL-REC2", fabric2)
        result = self.execute(fabric2, self.intent(grant2, "DEL-REC", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": sha
        }), "A-DEL-REC-2")
        self.assertTrue(result["actor_result"]["effect_marker_verified_in_latest_path_commit"])
        self.assertTrue(result["actor_result"]["recovered_from_provider_state"])
        self.assertEqual(1, self.transport.delete_calls)

    def test_absent_target_without_effect_marker_is_not_falsely_attributed(self):
        branch, path, sha = "third-wish-disposable/foreign", ".third-wish-disposable/foreign.txt", "e" * 40
        self.transport.seed_file(branch, path, sha)
        grant = self.grant("GITHUB.DESTRUCTIVE", "FOREIGN")
        action = self.intent(grant, "DEL-FOREIGN", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": sha
        })
        self.broker._bind(action)
        self.broker.effect_store.update(action.request_id, state="EFFECT_ENTERING")
        del self.transport.contents[(branch, path)]
        self.transport.path_commits[(branch, path)] = [{"sha": "f" * 40, "commit": {"message": "foreign cleanup"}}]
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "FOREIGN2", fabric2)
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(fabric2, self.intent(grant2, "DEL-FOREIGN", "DELETE_FILE_DISPOSABLE_BRANCH", {
                "branch": branch, "path": path, "expected_sha": sha
            }), "A-FOREIGN")
        self.assertEqual(0, self.transport.delete_calls)
        self.assertEqual("EFFECT_ENTERING", self.broker.effect_store.get(action.request_id)["state"])

    def test_destructive_before_apply_failure_reconciles_no_effect_without_retry(self):
        branch, path, sha = "third-wish-disposable/no-effect", ".third-wish-disposable/no-effect.txt", "1" * 40
        self.transport.seed_file(branch, path, sha)
        self.transport.fail_delete_before_apply = True
        grant = self.grant("GITHUB.DESTRUCTIVE", "DEL-NO")
        action = self.intent(grant, "DEL-NO", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": sha
        })
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "A-DEL-NO-1")
        self.transport.fail_delete_before_apply = False
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "DEL-NO2", fabric2)
        result = self.execute(fabric2, self.intent(grant2, "DEL-NO", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": sha
        }), "A-DEL-NO-2")
        self.assertTrue(result["actor_result"]["authoritative_no_effect_established"])
        self.assertFalse(result["actor_result"]["same_request_auto_retry"])
        self.assertEqual(1, self.transport.delete_calls)

    def test_changed_persistent_binding_rejects_before_effect(self):
        branch, path, sha = "third-wish-disposable/bind", ".third-wish-disposable/bind.txt", "2" * 40
        self.transport.seed_file(branch, path, sha)
        grant = self.grant("GITHUB.DESTRUCTIVE", "PERSIST")
        self.execute(self.fabric, self.intent(grant, "PERSIST", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": branch, "path": path, "expected_sha": sha
        }), "A-PERSIST-1")
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "PERSIST2", fabric2)
        changed = self.intent(grant2, "PERSIST", "DELETE_FILE_DISPOSABLE_BRANCH", {
            "branch": "third-wish-disposable/other", "path": ".third-wish-disposable/other.txt", "expected_sha": "3" * 40
        })
        result = self.execute(fabric2, changed, "A-PERSIST-2")
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])
        self.assertEqual(1, self.transport.delete_calls)

    def test_durable_store_uses_hash_binding_not_raw_parameters(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "STORE")
        old, marker = self.transport.description, "RAW_DESCRIPTION_MARKER_V1846"
        self.execute(self.fabric, self.intent(grant, "STORE", "SET_DESCRIPTION_CAS", {
            "expected_description": old, "new_description": marker
        }), "A-STORE")
        raw = self.broker.effect_store.path.read_text(encoding="utf-8")
        self.assertNotIn(old, raw)
        self.assertNotIn(marker, raw)
        row = json.loads(raw)["requests"]["STORE"]
        self.assertIn("binding_sha256", row)
        self.assertNotIn("parameters", row)
        self.assertNotIn("raw_parameters", row)


if __name__ == "__main__":
    unittest.main()
