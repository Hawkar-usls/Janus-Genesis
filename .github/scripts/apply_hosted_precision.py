from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "genesis_v18_7_20_hosted_pilgrimage.py"
TESTS = ROOT / "tests" / "test_genesis_v18_7_20_hosted_pilgrimage.py"
DOCS = ROOT / "docs" / "GENESIS_V18_7_20_ONE_LINK_HOSTED_PILGRIMAGE.md"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


text = CORE.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''class HostedIdempotencyError(HostedBridgeError):
    code = "HOSTED_IDEMPOTENCY_CONFLICT"


class HostedUnavailableError(HostedBridgeError):
''',
    '''class HostedIdempotencyError(HostedBridgeError):
    code = "HOSTED_IDEMPOTENCY_CONFLICT"


class HostedRecoveryRequired(HostedBridgeError):
    code = "HOSTED_IDEMPOTENCY_RECOVERY_REQUIRED"


class HostedUnavailableError(HostedBridgeError):
''',
    "insert recovery error",
)

text = replace_once(
    text,
    '''    @property
    def authoritative_available(self) -> bool:
        return bool(self.config.live_mode and not self.kill_switch_active)
''',
    '''    def _gateway_integrity(self) -> dict[str, Any]:
        try:
            value = self.gateway.verify_store()
        except Exception as exc:
            return {
                "valid": False,
                "errors": [f"gateway_integrity_exception:{type(exc).__name__}"],
            }
        if not isinstance(value, dict):
            return {"valid": False, "errors": ["gateway_integrity_shape"]}
        return value

    def _hosted_recovery_required_count(self) -> int:
        try:
            store = self._load()
        except Exception:
            return 1
        return sum(
            isinstance(record, dict) and record.get("state") == "IN_FLIGHT"
            for record in store["idempotency"].values()
        )

    def _base_runtime_available(self) -> bool:
        hosted = self.verify_store()
        return bool(
            self.config.live_mode
            and not self.kill_switch_active
            and self._gateway_integrity().get("valid") is True
            and hosted.get("valid") is True
        )

    @property
    def authoritative_available(self) -> bool:
        return bool(
            self._base_runtime_available()
            and self._hosted_recovery_required_count() == 0
        )
''',
    "gate availability",
)

health_start = text.index("    def health(self) -> dict[str, Any]:")
health_end = text.index("\n    @staticmethod\n    def _client_hash", health_start)
text = (
    text[:health_start]
    + '''    def health(self) -> dict[str, Any]:
        gateway_integrity = self._gateway_integrity()
        hosted_integrity = self.verify_store()
        recovery_required = int(hosted_integrity.get("recovery_required_count", 0))
        available = bool(
            self.config.live_mode
            and not self.kill_switch_active
            and gateway_integrity.get("valid") is True
            and hosted_integrity.get("valid") is True
            and recovery_required == 0
        )
        if gateway_integrity.get("valid") is not True:
            status = "FAILED_GATEWAY_INTEGRITY"
        elif hosted_integrity.get("valid") is not True:
            status = "FAILED_HOSTED_INTEGRITY"
        elif recovery_required:
            status = "RECOVERY_REQUIRED"
        elif available:
            status = "READY"
        else:
            status = "DEGRADED"
        return {
            "schema": "janus.genesis.hosted_health.v1",
            "version": HOSTED_BRIDGE_VERSION,
            "status": status,
            "live_mode": self.config.live_mode,
            "kill_switch": self.kill_switch_active,
            "authoritative_runtime_available": available,
            "narrative_fallback_available": self.config.allow_narrative_fallback,
            "gateway_integrity_valid": gateway_integrity.get("valid") is True,
            "hosted_integrity_valid": hosted_integrity.get("valid") is True,
            "idempotency_recovery_required": recovery_required,
        }
'''
    + text[health_end:]
)

text = replace_once(
    text,
    '''    def _fallback_start(
        self,
        payload: dict[str, Any],
        *,
        reason: str,
    ) -> dict[str, Any]:
''',
    '''    def _stateless_fallback_start(
        self,
        *,
        reason: str,
    ) -> dict[str, Any]:
        if not self.config.allow_narrative_fallback:
            raise HostedUnavailableError(reason)
        return {
            "status": STATUS_FALLBACK,
            "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
            "authoritative_runtime_available": False,
            "fallback_used": True,
            "fallback_reason": reason,
            "session": None,
            "session_token": None,
            "local_narrative_required": True,
            "authoritative_runtime": False,
            "canonical_runtime_outcome_recorded": False,
            "canonical_state_change_claimed": False,
        }

    def _fallback_start(
        self,
        payload: dict[str, Any],
        *,
        reason: str,
    ) -> dict[str, Any]:
''',
    "insert stateless fallback",
)

text = replace_once(
    text,
    '''        if requested_mode == MODE_AUTHORITATIVE and not self.authoritative_available:
            reason = "KILL_SWITCH_ACTIVE" if self.kill_switch_active else "LIVE_MODE_DISABLED"
            return self._fallback_start(payload, reason=reason)
''',
    '''        if requested_mode == MODE_AUTHORITATIVE and not self.authoritative_available:
            gateway_integrity = self._gateway_integrity()
            hosted_integrity = self.verify_store()
            if gateway_integrity.get("valid") is not True:
                return self._stateless_fallback_start(
                    reason="GATEWAY_INTEGRITY_FAILED"
                )
            if hosted_integrity.get("valid") is not True:
                return self._stateless_fallback_start(
                    reason="HOSTED_INTEGRITY_FAILED"
                )
            if int(hosted_integrity.get("recovery_required_count", 0)):
                return self._stateless_fallback_start(
                    reason="IDEMPOTENCY_RECOVERY_REQUIRED"
                )
            reason = "KILL_SWITCH_ACTIVE" if self.kill_switch_active else "LIVE_MODE_DISABLED"
            return self._fallback_start(payload, reason=reason)
''',
    "safe start fallback",
)

text = replace_once(
    text,
    '''    def _authorize(
        self,
        token: str,
        *,
        scope: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        claims = self.signer.verify(token, required_scope=scope)
        session = self.gateway.session_state(claims["sid"])
''',
    '''    def _authorize(
        self,
        token: str,
        *,
        scope: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        claims = self.signer.verify(token, required_scope=scope)
        if self._gateway_integrity().get("valid") is not True:
            raise HostedUnavailableError("HOSTED_GATEWAY_INTEGRITY_FAILED")
        session = self.gateway.session_state(claims["sid"])
''',
    "authorize integrity gate",
)

process_start = text.index("    def process_turn(")
process_end = text.index("\n    def session_state(", process_start)
new_process = '''    def _record_runtime_fallback_claims(
        self,
        *,
        claims: dict[str, Any],
        action: str,
        reason: str,
    ) -> dict[str, Any]:
        event = {
            "at": int(self.clock()),
            "session_sha256": hashlib.sha256(
                str(claims["sid"]).encode("utf-8")
            ).hexdigest(),
            "actor_sha256": hashlib.sha256(
                str(claims["aid"]).encode("utf-8")
            ).hexdigest(),
            "action_sha256": hashlib.sha256(action.encode("utf-8")).hexdigest(),
            "reason": reason,
        }
        with self._lock:
            store = self._load()
            store["fallback_events"].append(event)
            store["fallback_events"] = store["fallback_events"][-1000:]
            self._write(store)
        return {
            "status": STATUS_FALLBACK,
            "runtime_status": MODE_NARRATIVE,
            "authoritative_runtime": False,
            "canonical_runtime_outcome_recorded": False,
            "canonical_state_change_claimed": False,
            "fallback_reason": reason,
            "retryable_when_runtime_returns": reason not in {
                "GATEWAY_INTEGRITY_FAILED",
                "HOSTED_INTEGRITY_FAILED",
                "IDEMPOTENCY_RECOVERY_REQUIRED",
            },
            "action_sha256": event["action_sha256"],
            "narrative": (
                "Авторитетный host сейчас недоступен. Ход не применён к каноническому "
                "Genesis. Его можно продолжить только как явно обозначенную narrative-сцену."
            ),
        }

    def _matching_inflight_turn(
        self,
        session_id: str,
        record: dict[str, Any],
    ) -> dict[str, Any] | None:
        state = self.gateway.session_state(session_id)
        matches = [
            turn
            for turn in state.get("turns", [])
            if turn.get("sequence") == record.get("expected_sequence")
            and turn.get("action_sha256") == record.get("action_sha256")
            and turn.get("origin") == record.get("origin")
            and turn.get("human_confirmed") == record.get("human_confirmed")
            and turn.get("previous_turn_hash")
            == record.get("expected_previous_turn_hash")
        ]
        if len(matches) > 1:
            raise HostedRecoveryRequired("HOSTED_MULTIPLE_RECOVERY_TURNS_FOUND")
        return copy.deepcopy(matches[0]) if matches else None

    def _commit_idempotency_record(
        self,
        store: dict[str, Any],
        cache_key: str,
        turn: dict[str, Any],
        *,
        recovered: bool,
    ) -> None:
        record = store["idempotency"][cache_key]
        record.update(
            {
                "state": "COMMITTED",
                "sequence": turn["sequence"],
                "turn_hash": turn["turn_hash"],
                "committed_at": int(self.clock()),
                "recovered_after_interruption": bool(recovered),
            }
        )
        self._write(store)

    def _recover_inflight_for_session(
        self,
        store: dict[str, Any],
        *,
        session_id: str,
    ) -> None:
        session_sha256 = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        changed = False
        for cache_key, record in store["idempotency"].items():
            if (
                isinstance(record, dict)
                and record.get("state") == "IN_FLIGHT"
                and record.get("session_sha256") == session_sha256
            ):
                turn = self._matching_inflight_turn(session_id, record)
                if turn is None:
                    raise HostedRecoveryRequired()
                record.update(
                    {
                        "state": "COMMITTED",
                        "sequence": turn["sequence"],
                        "turn_hash": turn["turn_hash"],
                        "committed_at": int(self.clock()),
                        "recovered_after_interruption": True,
                    }
                )
                changed = True
        if changed:
            self._write(store)

    def _replay_committed(
        self,
        *,
        claims: dict[str, Any],
        record: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.gateway.session_state(claims["sid"])
        matches = [
            item
            for item in state.get("turns", [])
            if item.get("sequence") == record.get("sequence")
            and item.get("turn_hash") == record.get("turn_hash")
        ]
        if len(matches) != 1:
            raise HostedRecoveryRequired("HOSTED_COMMITTED_TURN_NOT_FOUND")
        return {
            "status": STATUS_TURN_PROCESSED,
            "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
            "session_id": claims["sid"],
            "turn": copy.deepcopy(matches[0]),
            "idempotent_replay": True,
            "recovered_after_interruption": bool(
                record.get("recovered_after_interruption")
            ),
        }

    def _after_intent_before_runtime(self, record: dict[str, Any]) -> None:
        """Test hook; production implementation intentionally does nothing."""

    def _after_runtime_before_idempotency_commit(
        self,
        turn: dict[str, Any],
    ) -> None:
        """Test hook; production implementation intentionally does nothing."""

    def process_turn(
        self,
        token: str,
        payload: dict[str, Any],
        *,
        client_id: str,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("HOSTED_TURN_PAYLOAD_MUST_BE_OBJECT")
        claims = self.signer.verify(token, required_scope="turn")
        self._consume_rate(
            client_id=client_id,
            session_id=claims["sid"],
            operation="turn",
        )
        action = str(payload.get("action") or "").strip()
        if not action:
            raise ValueError("AI_LINK_EMPTY_ACTION")
        if len(action) > self.config.max_action_chars:
            raise ValueError("AI_LINK_ACTION_TOO_LONG")
        idempotency_key = str(payload.get("idempotency_key") or "").strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValueError("HOSTED_IDEMPOTENCY_KEY_REQUIRED")
        if self._gateway_integrity().get("valid") is not True:
            return self._record_runtime_fallback_claims(
                claims=claims,
                action=action,
                reason="GATEWAY_INTEGRITY_FAILED",
            )
        session = self.gateway.session_state(claims["sid"])
        if (
            session.get("session_id") != claims["sid"]
            or session.get("actor_id") != claims["aid"]
            or session.get("role") != claims["role"]
        ):
            raise HostedAuthenticationError("HOSTED_TOKEN_SESSION_BINDING_INVALID")
        default_origin = {
            ROLE_HUMAN_THROUGH_AI: ORIGIN_HUMAN,
            ROLE_AI_INTERFACE: ORIGIN_AI_PROPOSAL,
            ROLE_INDEPENDENT_AI: ORIGIN_AI_AUTONOMOUS,
        }[str(session["role"])]
        origin = str(payload.get("origin") or default_origin).strip().upper()
        human_confirmed = payload.get("human_confirmed", False)
        if type(human_confirmed) is not bool:
            raise TypeError("AI_LINK_HUMAN_CONFIRMATION_MUST_BE_BOOLEAN")
        self.gateway._validate_origin(session, origin, human_confirmed)
        request_fingerprint = _sha256(
            {
                "session_id": claims["sid"],
                "action": action,
                "origin": origin,
                "human_confirmed": human_confirmed,
            }
        )
        cache_key = hashlib.sha256(
            f"{claims['sid']}:{idempotency_key}".encode("utf-8")
        ).hexdigest()
        session_sha256 = hashlib.sha256(
            claims["sid"].encode("utf-8")
        ).hexdigest()

        with self._lock:
            store = self._load()
            self._recover_inflight_for_session(store, session_id=claims["sid"])
            store = self._load()
            existing = store["idempotency"].get(cache_key)
            if isinstance(existing, dict):
                if existing.get("request_sha256") != request_fingerprint:
                    raise HostedIdempotencyError()
                if existing.get("state") != "COMMITTED":
                    raise HostedRecoveryRequired()
                return self._replay_committed(claims=claims, record=existing)

            if session.get("execution_mode") == MODE_AUTHORITATIVE:
                if not self._base_runtime_available():
                    if self._gateway_integrity().get("valid") is not True:
                        reason = "GATEWAY_INTEGRITY_FAILED"
                    elif self.verify_store().get("valid") is not True:
                        reason = "HOSTED_INTEGRITY_FAILED"
                    elif self.kill_switch_active:
                        reason = "KILL_SWITCH_ACTIVE"
                    else:
                        reason = "LIVE_MODE_DISABLED"
                    return self._record_runtime_fallback_claims(
                        claims=claims,
                        action=action,
                        reason=reason,
                    )

            current_state = self.gateway.session_state(claims["sid"])
            previous_hash = (
                current_state["turns"][-1]["turn_hash"]
                if current_state.get("turns")
                else None
            )
            pending = {
                "state": "IN_FLIGHT",
                "request_sha256": request_fingerprint,
                "session_sha256": session_sha256,
                "action_sha256": hashlib.sha256(
                    action.encode("utf-8")
                ).hexdigest(),
                "origin": origin,
                "human_confirmed": human_confirmed,
                "expected_sequence": int(current_state.get("next_sequence", 1)),
                "expected_previous_turn_hash": previous_hash,
                "created_at": int(self.clock()),
            }
            store["idempotency"][cache_key] = pending
            self._write(store)
            self._after_intent_before_runtime(copy.deepcopy(pending))

            turn = self.gateway.process_turn(
                claims["sid"],
                action,
                origin=origin,
                human_confirmed=human_confirmed,
            )
            self._after_runtime_before_idempotency_commit(copy.deepcopy(turn))
            store = self._load()
            record = store["idempotency"].get(cache_key)
            if (
                not isinstance(record, dict)
                or record.get("state") != "IN_FLIGHT"
                or record.get("request_sha256") != request_fingerprint
            ):
                raise HostedRecoveryRequired("HOSTED_PENDING_RECEIPT_LOST")
            self._commit_idempotency_record(
                store,
                cache_key,
                turn,
                recovered=False,
            )
            if len(store["idempotency"]) > 10000:
                store = self._load()
                committed = [
                    (key, value)
                    for key, value in store["idempotency"].items()
                    if isinstance(value, dict)
                    and value.get("state") == "COMMITTED"
                ]
                committed.sort(
                    key=lambda item: int(item[1].get("committed_at", 0))
                )
                removable = {
                    key for key, _ in committed[: max(0, len(committed) - 8000)]
                }
                store["idempotency"] = {
                    key: value
                    for key, value in store["idempotency"].items()
                    if key not in removable
                }
                self._write(store)
            return {
                "status": STATUS_TURN_PROCESSED,
                "hosted_bridge_version": HOSTED_BRIDGE_VERSION,
                "session_id": claims["sid"],
                "turn": turn,
                "idempotent_replay": False,
                "recovered_after_interruption": False,
            }
'''
text = text[:process_start] + new_process + text[process_end:]

verify_start = text.index("    def verify_store(self) -> dict[str, Any]:")
new_verify = '''    def verify_store(self) -> dict[str, Any]:
        with self._lock:
            store = self._load()
        errors: list[str] = []
        recovery_required_count = 0
        for key, record in store["idempotency"].items():
            if not isinstance(key, str) or len(key) != 64:
                errors.append("idempotency_key_shape")
            if not isinstance(record, dict):
                errors.append(f"idempotency_record:{key}")
                continue
            state = record.get("state")
            if state not in {"IN_FLIGHT", "COMMITTED"}:
                errors.append(f"idempotency_state:{key}")
            if not isinstance(record.get("request_sha256"), str):
                errors.append(f"idempotency_request_hash:{key}")
            if not isinstance(record.get("session_sha256"), str):
                errors.append(f"idempotency_session_hash:{key}")
            if not isinstance(record.get("action_sha256"), str):
                errors.append(f"idempotency_action_hash:{key}")
            if not isinstance(record.get("created_at"), int):
                errors.append(f"idempotency_created_at:{key}")
            if state == "IN_FLIGHT":
                recovery_required_count += 1
                if not isinstance(record.get("expected_sequence"), int):
                    errors.append(f"idempotency_expected_sequence:{key}")
            if state == "COMMITTED":
                if not isinstance(record.get("sequence"), int):
                    errors.append(f"idempotency_sequence:{key}")
                if not isinstance(record.get("turn_hash"), str):
                    errors.append(f"idempotency_turn_hash:{key}")
        raw = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        valid = (
            not errors
            and "session_token" not in raw
            and '"action":' not in raw
        )
        return {
            "schema": "janus.genesis.hosted_integrity_audit.v1",
            "version": HOSTED_BRIDGE_VERSION,
            "idempotency_record_count": len(store["idempotency"]),
            "recovery_required_count": recovery_required_count,
            "operationally_ready": valid and recovery_required_count == 0,
            "rate_event_count": len(store["rate_events"]),
            "fallback_event_count": len(store["fallback_events"]),
            "raw_client_identifiers_present": False,
            "session_tokens_present": "session_token" in raw,
            "action_text_present": '"action":' in raw,
            "host_secret_present": False,
            "errors": errors,
            "valid": valid,
        }
'''
text = text[:verify_start] + new_verify
CORE.write_text(text, encoding="utf-8")

# Add regression imports and tests.
tests = TESTS.read_text(encoding="utf-8")
tests = replace_once(
    tests,
    '''    HostedPilgrimageBridge,
    HostedRateLimitError,
''',
    '''    HostedPilgrimageBridge,
    HostedRateLimitError,
    HostedRecoveryRequired,
''',
    "test recovery import",
)
insert_at = tests.index("\n\nif __name__ == \"__main__\":")
new_tests = '''

    def test_health_fails_closed_when_gateway_integrity_is_corrupt(self) -> None:
        started = self.start_independent()
        raw = json.loads(self.gateway.path.read_text(encoding="utf-8"))
        raw["sessions"][started["session"]["session_id"]]["session_hash"] = "tampered"
        self.gateway.path.write_text(
            json.dumps(raw, ensure_ascii=False), encoding="utf-8"
        )
        health = self.bridge.health()
        self.assertEqual(health["status"], "FAILED_GATEWAY_INTEGRITY")
        self.assertFalse(health["authoritative_runtime_available"])
        fallback = self.bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "No Write On Corruption",
                "provider": "p",
                "model": "m",
            },
            client_id="integrity-client",
        )
        self.assertEqual(fallback["status"], STATUS_FALLBACK)
        self.assertEqual(fallback["fallback_reason"], "GATEWAY_INTEGRITY_FAILED")
        self.assertIsNone(fallback["session"])
        self.assertIsNone(fallback["session_token"])

    def test_crash_after_runtime_recovers_receipt_without_duplicate(self) -> None:
        class CrashAfterRuntimeBridge(HostedPilgrimageBridge):
            crashed = False

            def _after_runtime_before_idempotency_commit(self, turn):
                if not self.crashed:
                    self.crashed = True
                    raise RuntimeError("SIMULATED_PROCESS_CRASH_AFTER_RUNTIME")

        bridge = CrashAfterRuntimeBridge(
            self.gateway,
            self.data_dir,
            signer=self.signer,
            config=self.config,
            clock=self.clock,
        )
        started = bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "Crash Witness",
                "provider": "p",
                "model": "m",
            },
            client_id="crash-client",
        )
        payload = {
            "action": "Войти в Пятый Берег",
            "idempotency_key": "crash-window-key",
        }
        with self.assertRaisesRegex(RuntimeError, "SIMULATED_PROCESS_CRASH"):
            bridge.process_turn(
                started["session_token"], payload, client_id="crash-client"
            )
        self.assertEqual(
            len(self.gateway.session_state(started["session"]["session_id"])["turns"]),
            1,
        )
        self.assertEqual(bridge.verify_store()["recovery_required_count"], 1)
        recovered = bridge.process_turn(
            started["session_token"], payload, client_id="crash-client"
        )
        self.assertTrue(recovered["idempotent_replay"])
        self.assertTrue(recovered["recovered_after_interruption"])
        self.assertEqual(
            len(self.gateway.session_state(started["session"]["session_id"])["turns"]),
            1,
        )
        self.assertEqual(bridge.verify_store()["recovery_required_count"], 0)

    def test_unresolved_inflight_intent_blocks_reexecution(self) -> None:
        class CrashBeforeRuntimeBridge(HostedPilgrimageBridge):
            def _after_intent_before_runtime(self, record):
                raise RuntimeError("SIMULATED_PROCESS_CRASH_BEFORE_RUNTIME")

        bridge = CrashBeforeRuntimeBridge(
            self.gateway,
            self.data_dir,
            signer=self.signer,
            config=self.config,
            clock=self.clock,
        )
        started = bridge.start_session(
            {
                "role": ROLE_INDEPENDENT_AI,
                "execution_mode": MODE_AUTHORITATIVE,
                "display_name": "Pending Witness",
                "provider": "p",
                "model": "m",
            },
            client_id="pending-client",
        )
        payload = {
            "action": "Войти в Пятый Берег",
            "idempotency_key": "pending-key",
        }
        with self.assertRaisesRegex(RuntimeError, "SIMULATED_PROCESS_CRASH"):
            bridge.process_turn(
                started["session_token"], payload, client_id="pending-client"
            )
        self.assertEqual(
            len(self.gateway.session_state(started["session"]["session_id"])["turns"]),
            0,
        )
        with self.assertRaises(HostedRecoveryRequired):
            bridge.process_turn(
                started["session_token"], payload, client_id="pending-client"
            )
        self.assertEqual(
            len(self.gateway.session_state(started["session"]["session_id"])["turns"]),
            0,
        )
        self.assertFalse(bridge.health()["authoritative_runtime_available"])
        self.assertEqual(bridge.health()["status"], "RECOVERY_REQUIRED")
'''
tests = tests[:insert_at] + new_tests + tests[insert_at:]
TESTS.write_text(tests, encoding="utf-8")

docs = DOCS.read_text(encoding="utf-8")
docs = replace_once(
    docs,
    '''- Every hosted turn requires an idempotency key.
- Repeating the same key and request returns the original turn.
- Reusing a key for a different request is rejected.
- Concurrent requests with the same key are serialized around the real world
  turn so only one can reach the runtime.
''',
    '''- Every hosted turn requires an idempotency key.
- A durable `IN_FLIGHT` intent is written before the real world turn.
- The receipt becomes `COMMITTED` only after the AI Link turn is persisted.
- After an interruption, an exact persisted turn repairs its receipt and is
  returned without executing again.
- If no exact turn can be proven, the session fails closed with
  `HOSTED_IDEMPOTENCY_RECOVERY_REQUIRED`; availability never wins over safety.
- Repeating the same committed key and request returns the original turn.
- Reusing a key for a different request is rejected.
- Concurrent requests with the same key are serialized around the real world
  turn so only one can reach the runtime.
''',
    "docs durable idempotency",
)
docs = replace_once(
    docs,
    '''- Live mode defaults off.
- The kill switch defaults on.
''',
    '''- Live mode defaults off.
- The kill switch defaults on.
- `authoritative_runtime_available` is false whenever AI Link integrity,
  hosted-store integrity, or idempotency recovery is not clean.
''',
    "docs integrity gate",
)
DOCS.write_text(docs, encoding="utf-8")

print("hosted precision patch applied")
