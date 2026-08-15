# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import unittest

from genesis_v18_7_40_third_wish_capability_fabric import (
    ActionIntent,
    CapabilityOutcomeUndetermined,
    THIRD_WISH_INTENT_SCHEMA,
    ThirdWishCapabilityFabric,
    issue_hawkar_third_wish_profile,
)
from tools.genesis_third_wish_github_broker import GitHubThirdWishBroker


class FakeTransport:
    def __init__(self) -> None:
        self.calls = []

    def request(self, method, path, *, payload=None, query=None):
        self.calls.append({"method": method, "path": path, "payload": payload, "query": query})
        if method == "GET" and path == "/repos/Hawkar-usls/Janus_Genesis":
            return {
                "name": "Janus_Genesis",
                "full_name": "Hawkar-usls/Janus_Genesis",
                "private": False,
                "default_branch": "main",
                "archived": False,
                "disabled": False,
                "visibility": "public",
                "updated_at": "2026-08-15T00:00:00Z",
            }
        if method == "GET" and "/contents/README.md" in path:
            return {
                "path": "README.md",
                "type": "file",
                "sha": "abc",
                "size": 12,
                "encoding": "base64",
                "content": base64.b64encode(b"hello janus\n").decode("ascii"),
            }
        if method == "GET" and path == "/search/code":
            return {
                "total_count": 1,
                "items": [
                    {
                        "name": "genesis.py",
                        "path": "genesis.py",
                        "sha": "code-sha",
                        "repository": {"full_name": "Hawkar-usls/Janus_Genesis"},
                    }
                ],
            }
        if method == "GET" and "/git/ref/heads/" in path:
            return {"object": {"sha": "base-sha"}}
        if method == "POST" and path.endswith("/git/refs"):
            return {"ref": payload["ref"], "object": {"sha": payload["sha"]}}
        if method == "PUT" and "/contents/" in path:
            return {"content": {"sha": "content-sha"}, "commit": {"sha": "commit-sha"}}
        if method == "POST" and path.endswith("/issues"):
            return {"number": 42, "state": "open", "title": payload["title"]}
        if method == "POST" and path.endswith("/pulls"):
            return {"number": 83, "state": "open", "title": payload["title"]}
        if method == "POST" and path.endswith("/issues/42/comments"):
            return {"id": 777, "created_at": "2026-08-15T00:00:00Z"}
        if method == "GET" and path.endswith("/issues/42"):
            return {"number": 42, "title": "Issue", "state": "open", "body": "body", "user": {"login": "Hawkar-usls"}}
        if method == "GET" and path.endswith("/pulls/83"):
            return {"number": 83, "title": "PR", "state": "open", "body": "body", "head": {"ref": "feature"}, "base": {"ref": "main"}}
        raise AssertionError((method, path, payload, query))


class GitHubThirdWishBrokerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport()
        self.fabric = ThirdWishCapabilityFabric(now_tick=lambda: 1_000)
        issue_hawkar_third_wish_profile(self.fabric)
        self.broker = GitHubThirdWishBroker(self.transport)
        self.broker.register(self.fabric)

    def _grant(self, capability_id):
        return next(g for g in self.fabric.grants.values() if g.capability_id == capability_id)

    def _intent(self, capability_id, operation, parameters=None, request_id=None, target="github:Hawkar-usls/Janus_Genesis"):
        grant = self._grant(capability_id)
        return ActionIntent(
            schema=THIRD_WISH_INTENT_SCHEMA,
            request_id=request_id or f"REQ-{capability_id}-{operation}",
            actor_id="JANUS",
            grant_id=grant.grant_id,
            capability_id=capability_id,
            target=target,
            operation=operation,
            purpose="broker test",
            parameters=dict(parameters or {}),
            origin="TEST",
        )

    def test_reference_adapter_registers_read_and_reversible_github_surface_only(self) -> None:
        for capability_id in GitHubThirdWishBroker.REGISTERED_CAPABILITIES:
            self.assertIn(capability_id, self.fabric.handlers)
        for capability_id in GitHubThirdWishBroker.INTENTIONALLY_UNREGISTERED_HIGH_IMPACT:
            self.assertNotIn(capability_id, self.fabric.handlers)

    def test_repository_metadata_and_content_read(self) -> None:
        meta = self.fabric.execute(self._intent("GITHUB.REPOSITORY.READ", "GET_REPOSITORY"))
        self.assertEqual(meta["actor_result"]["full_name"], "Hawkar-usls/Janus_Genesis")
        content = self.fabric.execute(
            self._intent(
                "GITHUB.REPOSITORY.READ",
                "GET_CONTENT",
                {"path": "README.md", "ref": "main"},
                request_id="REQ-CONTENT",
            )
        )
        self.assertEqual(content["actor_result"]["text"], "hello janus\n")
        self.assertNotIn("hello janus", str(self.fabric.ledger.events))

    def test_owner_wide_code_search(self) -> None:
        response = self.fabric.execute(
            self._intent(
                "GITHUB.CODE.SEARCH",
                "SEARCH",
                {"query": "Third Wish"},
                target="github:Hawkar-usls/*",
            )
        )
        self.assertEqual(response["actor_result"]["total_count"], 1)
        self.assertIn("user:Hawkar-usls", self.transport.calls[-1]["query"]["q"])

    def test_branch_create_and_file_write_are_typed_parameterized_effects(self) -> None:
        branch = self.fabric.execute(
            self._intent(
                "GITHUB.BRANCH.CREATE",
                "CREATE_BRANCH",
                {"new_branch": "janus/third-wish-test", "from_ref": "main"},
            )
        )
        self.assertEqual(branch["actor_result"]["source_sha"], "base-sha")
        text = "generated source payload"
        written = self.fabric.execute(
            self._intent(
                "GITHUB.FILE.WRITE_BRANCH",
                "WRITE_FILE",
                {
                    "path": "generated/test.txt",
                    "branch": "janus/third-wish-test",
                    "content": text,
                    "message": "Third Wish test",
                },
                request_id="REQ-WRITE",
            )
        )
        self.assertEqual(written["actor_result"]["commit_sha"], "commit-sha")
        self.assertNotIn(text, str(self.fabric.ledger.events))
        put_call = next(call for call in self.transport.calls if call["method"] == "PUT")
        self.assertNotEqual(put_call["payload"]["content"], text)

    def test_issue_pr_and_comment_creation(self) -> None:
        issue = self.fabric.execute(
            self._intent(
                "GITHUB.ISSUE.CREATE",
                "CREATE_ISSUE",
                {"title": "Third Wish issue", "body": "body"},
            )
        )
        self.assertEqual(issue["actor_result"]["number"], 42)
        pr = self.fabric.execute(
            self._intent(
                "GITHUB.PR.CREATE",
                "CREATE_PR",
                {"title": "Third Wish PR", "head": "janus/third-wish-test", "base": "main", "body": "body"},
            )
        )
        self.assertEqual(pr["actor_result"]["number"], 83)
        comment = self.fabric.execute(
            self._intent(
                "GITHUB.COMMENT.CREATE",
                "CREATE_COMMENT",
                {"number": 42, "body": "comment"},
            )
        )
        self.assertEqual(comment["actor_result"]["comment_id"], 777)

    def test_sensitive_credential_paths_fail_before_transport_call(self) -> None:
        before = len(self.transport.calls)
        with self.assertRaises(CapabilityOutcomeUndetermined):
            self.fabric.execute(
                self._intent(
                    "GITHUB.REPOSITORY.READ",
                    "GET_CONTENT",
                    {"path": ".env"},
                    request_id="REQ-SENSITIVE",
                )
            )
        self.assertEqual(len(self.transport.calls), before)
        self.assertNotIn(".env", str(self.fabric.ledger.events[-1]))


if __name__ == "__main__":
    unittest.main()
