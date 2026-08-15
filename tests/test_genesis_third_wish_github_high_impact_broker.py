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
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
)
from tools.genesis_third_wish_github_broker import GitHubBrokerError
from tools.genesis_third_wish_github_high_impact_broker import (
    GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY,
    GITHUB_HIGH_IMPACT_REAUTH_SCHEMA,
    BoundGitHubHighImpactReauthorizationVerifier,
    GitHubHighImpactThirdWishBroker,
    _canonical,
)


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
    def _repo_base() -> str:
        return "/repos/Hawkar-usls/Janus_Genesis"

    def seed_file(self, *, branch: str, path: str, sha: str = "a" * 40) -> None:
        self.contents[(branch, path)] = {
            "type": "file",
            "path": path,
            "sha": sha,
            "size": 12,
        }

    def request(self, method, path, *, payload=None, query=None):
        method = str(method).upper()
        self.calls.append({
            "method": method,
            "path": str(path),
            "payload": copy.deepcopy(payload),
            "query": copy.deepcopy(query),
        })
        base = self._repo_base()

        if method == "GET" and path == base:
            return {
                "name": "Janus_Genesis",
                "full_name": "Hawkar-usls/Janus_Genesis",
                "description": self.description,
            }

        if method == "PATCH" and path == base:
            self.patch_calls += 1
            if self.fail_patch_before_apply:
                raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:injected-before-admin")
            self.description = None if payload.get("description") is None else str(payload.get("description"))
            if self.fail_patch_after_apply:
                raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:injected-after-admin")
            return {
                "name": "Janus_Genesis",
                "full_name": "Hawkar-usls/Janus_Genesis",
                "description": self.description,
            }

        content_prefix = base + "/contents/"
        if path.startswith(content_prefix):
            repo_path = path[len(content_prefix):]
            from urllib.parse import unquote
            repo_path = "/".join(unquote(part) for part in repo_path.split("/"))
            branch = str((query or {}).get("ref") or (payload or {}).get("branch") or "main")
            key = (branch, repo_path)
            if method == "GET":
                row = self.contents.get(key)
                if row is None:
                    raise GitHubBrokerError("GITHUB_HTTP_404:not-found")
                return copy.deepcopy(row)
            if method == "DELETE":
                self.delete_calls += 1
                if self.fail_delete_before_apply:
                    raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:injected-before-delete")
                row = self.contents.get(key)
                if row is None:
                    raise GitHubBrokerError("GITHUB_HTTP_404:not-found")
                if str(payload.get("sha")) != str(row.get("sha")):
                    raise GitHubBrokerError("GITHUB_HTTP_409:sha-mismatch")
                del self.contents[key]
                commit_sha = hashlib.sha1(
                    (branch + repo_path + str(payload.get("message"))).encode("utf-8")
                ).hexdigest()
                self.path_commits.setdefault(key, []).insert(0, {
                    "sha": commit_sha,
                    "commit": {"message": str(payload.get("message"))},
                })
                if self.fail_delete_after_apply:
                    raise GitHubBrokerError("GITHUB_CONNECTION_ERROR:injected-after-delete")
                return {"commit": {"sha": commit_sha}, "content": None}

        if method == "GET" and path == base + "/commits":
            branch = str((query or {}).get("sha") or "main")
            repo_path = str((query or {}).get("path") or "")
            rows = self.path_commits.get((branch, repo_path), [])
            return copy.deepcopy(rows[:1])

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
            key_env=self.key_env,
            now_tick=lambda: self.now,
            max_window_ticks=5000,
        )
        self.broker = GitHubHighImpactThirdWishBroker(
            transport=self.transport,
            data_dir=self.root,
        )
        self.fabric = self.new_fabric()

    def tearDown(self):
        os.environ.pop(self.key_env, None)
        self.temp.cleanup()

    def new_fabric(self):
        fabric = ThirdWishCapabilityFabric(
            now_tick=lambda: self.now,
            reauthorization_verifier=self.verifier,
        )
        self.broker.register(fabric)
        return fabric

    def grant(self, capability, suffix, fabric=None):
        fabric = fabric or self.fabric
        return fabric.issue_grant(
            grant_id=f"G-{suffix}",
            actor_id="JANUS",
            capability_id=capability,
            resource_pattern="github:Hawkar-usls/Janus_Genesis",
            source="V1846_TEST",
        )

    @staticmethod
    def intent(grant, request_id, operation, parameters):
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id,
            actor_id="JANUS",
            grant_id=grant.grant_id,
            capability_id=grant.capability_id,
            target="github:Hawkar-usls/Janus_Genesis",
            operation=operation,
            purpose="exercise final Third Wish high-impact boundary",
            parameters=parameters,
            origin="V1846_TEST",
        )

    def approval(self, action, approval_id):
        evidence = {
            "schema": GITHUB_HIGH_IMPACT_REAUTH_SCHEMA,
            "approval_id": approval_id,
            "issued_at_tick": self.now - 10,
            "expires_at_tick": self.now + 1000,
        }
        unsigned = self.verifier.unsigned_payload(action, evidence)
        evidence["approval_signature"] = hmac.new(
            os.environ[self.key_env].encode("utf-8"),
            _canonical(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return evidence

    def execute(self, fabric, action, approval_id):
        return fabric.execute(
            action,
            human_reauthorization=self.approval(action, approval_id),
        )

    def test_exact_final_surface_and_claim_ceiling(self):
        self.assertEqual(
            {"GITHUB.REPOSITORY.ADMIN", "GITHUB.DESTRUCTIVE"},
            set(self.fabric.handlers),
        )
        self.assertEqual(2, GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY["registered_capability_count"])
        self.assertFalse(GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY["delete_repository_supported"])
        self.assertFalse(GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY["delete_protected_branch_supported"])
        self.assertFalse(GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY["force_push_supported"])
        self.assertFalse(GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY["effect_entering_auto_retry"])
        self.assertFalse(
            GITHUB_HIGH_IMPACT_CLAIM_BOUNDARY[
                "destructive_capability_requires_destroying_valuable_state"
            ]
        )

    def test_broker_refuses_weak_reauthorization_verifier(self):
        weak = ThirdWishCapabilityFabric(
            now_tick=lambda: self.now,
            reauthorization_verifier=lambda intent, evidence: bool(evidence.get("approved")),
        )
        with self.assertRaises(CapabilityDenied):
            self.broker.register(weak)

    def test_reauthorization_is_bound_to_exact_destructive_target(self):
        grant = self.grant("GITHUB.DESTRUCTIVE", "REAUTH-BIND")
        first = self.intent(
            grant,
            "DELETE-BIND-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {
                "branch": "third-wish-disposable/one",
                "path": ".third-wish-disposable/one.txt",
                "expected_sha": "a" * 40,
            },
        )
        evidence = self.approval(first, "APPROVAL-BIND")
        changed = self.intent(
            grant,
            "DELETE-BIND-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {
                "branch": "third-wish-disposable/two",
                "path": ".third-wish-disposable/two.txt",
                "expected_sha": "b" * 40,
            },
        )
        result = self.fabric.execute(changed, human_reauthorization=evidence)
        self.assertEqual("FRESH_HUMAN_REAUTHORIZATION_REQUIRED", result["status"])
        self.assertFalse(result["effect_executed"])
        self.assertEqual(0, self.transport.delete_calls)

    def test_protected_and_non_disposable_destructive_targets_reject_pre_effect(self):
        grant = self.grant("GITHUB.DESTRUCTIVE", "BLOCK")
        attempts = [
            {
                "branch": "main",
                "path": ".third-wish-disposable/x.txt",
                "expected_sha": "a" * 40,
            },
            {
                "branch": "feature/not-disposable",
                "path": ".third-wish-disposable/x.txt",
                "expected_sha": "a" * 40,
            },
            {
                "branch": "third-wish-disposable/x",
                "path": "valuable.txt",
                "expected_sha": "a" * 40,
            },
        ]
        for index, params in enumerate(attempts):
            action = self.intent(
                grant,
                f"BLOCK-{index}",
                "DELETE_FILE_DISPOSABLE_BRANCH",
                params,
            )
            result = self.execute(self.fabric, action, f"APPROVAL-BLOCK-{index}")
            self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
            self.assertFalse(result["external_call_entered"])
        self.assertEqual(0, self.transport.delete_calls)

    def test_delete_repository_and_force_push_are_not_reference_operations(self):
        grant = self.grant("GITHUB.DESTRUCTIVE", "UNSUPPORTED")
        for operation in ("DELETE_REPOSITORY", "DELETE_BRANCH", "FORCE_PUSH"):
            action = self.intent(
                grant,
                f"UNSUPPORTED-{operation}",
                operation,
                {},
            )
            result = self.execute(self.fabric, action, f"APPROVAL-{operation}")
            self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
            self.assertFalse(result["external_call_entered"])

    def test_admin_cas_mismatch_is_known_non_effect_without_patch(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-CAS")
        action = self.intent(
            grant,
            "ADMIN-CAS-MISMATCH",
            "SET_DESCRIPTION_CAS",
            {
                "expected_description": "not-current",
                "new_description": "new value",
            },
        )
        result = self.execute(self.fabric, action, "APPROVAL-ADMIN-CAS")
        actor = result["actor_result"]
        self.assertEqual("SETTLED", result["status"])
        self.assertFalse(actor["admin_effect_established"])
        self.assertFalse(actor["precondition_matched"])
        self.assertEqual(0, self.transport.patch_calls)

    def test_admin_cas_success_and_no_raw_description_in_store(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-SUCCESS")
        old = self.transport.description
        new = "replacement description"
        action = self.intent(
            grant,
            "ADMIN-SUCCESS-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": old, "new_description": new},
        )
        result = self.execute(self.fabric, action, "APPROVAL-ADMIN-SUCCESS")
        actor = result["actor_result"]
        self.assertTrue(actor["admin_effect_established"])
        self.assertTrue(actor["precondition_matched"])
        self.assertFalse(actor["no_net_change_probe"])
        self.assertEqual(new, self.transport.description)
        self.assertEqual(1, self.transport.patch_calls)
        store = self.broker.effect_store.path.read_text(encoding="utf-8")
        self.assertNotIn(old, store)
        self.assertNotIn(new, store)

    def test_admin_lost_response_recovers_settled_without_second_patch(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-RECOVER")
        old = self.transport.description
        new = "changed-on-provider"
        self.transport.fail_patch_after_apply = True
        action = self.intent(
            grant,
            "ADMIN-RECOVER-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": old, "new_description": new},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "APPROVAL-ADMIN-RECOVER-1")
        self.assertEqual(1, self.transport.patch_calls)
        self.assertEqual(new, self.transport.description)
        self.transport.fail_patch_after_apply = False

        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-RECOVER2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "ADMIN-RECOVER-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": old, "new_description": new},
        )
        result = self.execute(fabric2, replay, "APPROVAL-ADMIN-RECOVER-2")
        self.assertTrue(result["actor_result"]["admin_effect_established"])
        self.assertTrue(result["actor_result"]["recovered_from_provider_state"])
        self.assertEqual(1, self.transport.patch_calls)

    def test_admin_lost_response_before_effect_becomes_proven_no_effect_not_retry(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NO-EFFECT")
        old = self.transport.description
        new = "should-not-apply"
        self.transport.fail_patch_before_apply = True
        action = self.intent(
            grant,
            "ADMIN-NO-EFFECT-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": old, "new_description": new},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "APPROVAL-ADMIN-NO-EFFECT-1")
        self.assertEqual(old, self.transport.description)
        self.assertEqual(1, self.transport.patch_calls)
        self.transport.fail_patch_before_apply = False

        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NO-EFFECT2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "ADMIN-NO-EFFECT-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": old, "new_description": new},
        )
        result = self.execute(fabric2, replay, "APPROVAL-ADMIN-NO-EFFECT-2")
        actor = result["actor_result"]
        self.assertFalse(actor["admin_effect_established"])
        self.assertTrue(actor["authoritative_no_effect_established"])
        self.assertFalse(actor["same_request_auto_retry"])
        self.assertEqual(1, self.transport.patch_calls)

    def test_admin_no_net_change_lost_response_stays_unknown_and_no_retry(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NO-NET")
        current = self.transport.description
        self.transport.fail_patch_after_apply = True
        action = self.intent(
            grant,
            "ADMIN-NO-NET-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": current, "new_description": current},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "APPROVAL-ADMIN-NO-NET-1")
        self.assertEqual(1, self.transport.patch_calls)
        self.transport.fail_patch_after_apply = False

        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.REPOSITORY.ADMIN", "ADMIN-NO-NET2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "ADMIN-NO-NET-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": current, "new_description": current},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(fabric2, replay, "APPROVAL-ADMIN-NO-NET-2")
        self.assertEqual(1, self.transport.patch_calls)

    def test_destructive_sha_mismatch_is_non_effect_without_delete(self):
        branch = "third-wish-disposable/sha-mismatch"
        path = ".third-wish-disposable/x.txt"
        self.transport.seed_file(branch=branch, path=path, sha="a" * 40)
        grant = self.grant("GITHUB.DESTRUCTIVE", "SHA-MISMATCH")
        action = self.intent(
            grant,
            "DELETE-SHA-MISMATCH",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": "b" * 40},
        )
        result = self.execute(self.fabric, action, "APPROVAL-SHA-MISMATCH")
        self.assertFalse(result["actor_result"]["destructive_effect_established"])
        self.assertFalse(result["actor_result"]["precondition_matched"])
        self.assertEqual(0, self.transport.delete_calls)
        self.assertIn((branch, path), self.transport.contents)

    def test_destructive_success_is_disposable_and_effect_marked(self):
        branch = "third-wish-disposable/success"
        path = ".third-wish-disposable/success.txt"
        sha = "c" * 40
        self.transport.seed_file(branch=branch, path=path, sha=sha)
        grant = self.grant("GITHUB.DESTRUCTIVE", "DELETE-SUCCESS")
        action = self.intent(
            grant,
            "DELETE-SUCCESS-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        result = self.execute(self.fabric, action, "APPROVAL-DELETE-SUCCESS")
        actor = result["actor_result"]
        self.assertTrue(actor["destructive_effect_established"])
        self.assertFalse(actor["protected_branch_touched"])
        self.assertTrue(actor["disposable_branch_required"])
        self.assertTrue(actor["disposable_path_required"])
        self.assertRegex(actor["effect_marker"], r"^\[JANUS_EFFECT:[0-9a-f]{16}\]$")
        self.assertNotIn((branch, path), self.transport.contents)
        self.assertEqual(1, self.transport.delete_calls)

    def test_destructive_lost_response_recovers_by_effect_marker_without_second_delete(self):
        branch = "third-wish-disposable/recover"
        path = ".third-wish-disposable/recover.txt"
        sha = "d" * 40
        self.transport.seed_file(branch=branch, path=path, sha=sha)
        self.transport.fail_delete_after_apply = True
        grant = self.grant("GITHUB.DESTRUCTIVE", "DELETE-RECOVER")
        action = self.intent(
            grant,
            "DELETE-RECOVER-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "APPROVAL-DELETE-RECOVER-1")
        self.assertEqual(1, self.transport.delete_calls)
        self.assertNotIn((branch, path), self.transport.contents)
        self.transport.fail_delete_after_apply = False

        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "DELETE-RECOVER2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "DELETE-RECOVER-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        result = self.execute(fabric2, replay, "APPROVAL-DELETE-RECOVER-2")
        actor = result["actor_result"]
        self.assertTrue(actor["destructive_effect_established"])
        self.assertTrue(actor["effect_marker_verified_in_latest_path_commit"])
        self.assertTrue(actor["recovered_from_provider_state"])
        self.assertEqual(1, self.transport.delete_calls)

    def test_absent_target_without_effect_marker_is_not_falsely_attributed(self):
        branch = "third-wish-disposable/foreign-delete"
        path = ".third-wish-disposable/foreign.txt"
        sha = "e" * 40
        self.transport.seed_file(branch=branch, path=path, sha=sha)
        grant = self.grant("GITHUB.DESTRUCTIVE", "FOREIGN")
        action = self.intent(
            grant,
            "DELETE-FOREIGN-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        # Manually bind + mark EFFECT_ENTERING, then simulate another actor deleting
        # with an unrelated commit message.
        stored = self.broker._bind(action)
        self.broker.effect_store.update(action.request_id, state="EFFECT_ENTERING")
        del self.transport.contents[(branch, path)]
        self.transport.path_commits[(branch, path)] = [{
            "sha": "f" * 40,
            "commit": {"message": "foreign cleanup without JANUS marker"},
        }]
        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "FOREIGN2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "DELETE-FOREIGN-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(fabric2, replay, "APPROVAL-FOREIGN")
        self.assertEqual(0, self.transport.delete_calls)
        self.assertEqual("EFFECT_ENTERING", stored["state"])

    def test_destructive_before_effect_failure_reconciles_no_effect_without_retry(self):
        branch = "third-wish-disposable/no-effect"
        path = ".third-wish-disposable/no-effect.txt"
        sha = "1" * 40
        self.transport.seed_file(branch=branch, path=path, sha=sha)
        self.transport.fail_delete_before_apply = True
        grant = self.grant("GITHUB.DESTRUCTIVE", "DELETE-NO-EFFECT")
        action = self.intent(
            grant,
            "DELETE-NO-EFFECT-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.execute(self.fabric, action, "APPROVAL-DELETE-NO-EFFECT-1")
        self.assertEqual(1, self.transport.delete_calls)
        self.assertIn((branch, path), self.transport.contents)
        self.transport.fail_delete_before_apply = False

        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "DELETE-NO-EFFECT2", fabric=fabric2)
        replay = self.intent(
            grant2,
            "DELETE-NO-EFFECT-1",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        result = self.execute(fabric2, replay, "APPROVAL-DELETE-NO-EFFECT-2")
        actor = result["actor_result"]
        self.assertFalse(actor["destructive_effect_established"])
        self.assertTrue(actor["authoritative_no_effect_established"])
        self.assertFalse(actor["same_request_auto_retry"])
        self.assertEqual(1, self.transport.delete_calls)

    def test_changed_persistent_request_binding_is_pre_effect_rejected(self):
        branch = "third-wish-disposable/binding"
        path = ".third-wish-disposable/binding.txt"
        sha = "2" * 40
        self.transport.seed_file(branch=branch, path=path, sha=sha)
        grant = self.grant("GITHUB.DESTRUCTIVE", "BINDING")
        original = self.intent(
            grant,
            "DELETE-BINDING-STABLE",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {"branch": branch, "path": path, "expected_sha": sha},
        )
        self.execute(self.fabric, original, "APPROVAL-BINDING-1")

        fabric2 = self.new_fabric()
        grant2 = self.grant("GITHUB.DESTRUCTIVE", "BINDING2", fabric=fabric2)
        changed = self.intent(
            grant2,
            "DELETE-BINDING-STABLE",
            "DELETE_FILE_DISPOSABLE_BRANCH",
            {
                "branch": "third-wish-disposable/other",
                "path": ".third-wish-disposable/other.txt",
                "expected_sha": "3" * 40,
            },
        )
        result = self.execute(fabric2, changed, "APPROVAL-BINDING-2")
        self.assertEqual("PRE_EFFECT_REJECTED", result["status"])
        self.assertFalse(result["external_call_entered"])
        self.assertEqual(1, self.transport.delete_calls)

    def test_store_has_hash_binding_not_raw_parameters(self):
        grant = self.grant("GITHUB.REPOSITORY.ADMIN", "STORE")
        old = self.transport.description
        new = "STORE_RAW_DESCRIPTION_MARKER"
        action = self.intent(
            grant,
            "ADMIN-STORE-1",
            "SET_DESCRIPTION_CAS",
            {"expected_description": old, "new_description": new},
        )
        self.execute(self.fabric, action, "APPROVAL-STORE")
        raw = self.broker.effect_store.path.read_text(encoding="utf-8")
        self.assertNotIn(old, raw)
        self.assertNotIn(new, raw)
        state = json.loads(raw)
        row = state["requests"]["ADMIN-STORE-1"]
        self.assertIn("binding_sha256", row)
        self.assertNotIn("parameters", row)
        self.assertNotIn("raw_parameters", row)


if __name__ == "__main__":
    unittest.main()
