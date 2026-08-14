from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis_v18_7_19_ai_link_play import (
    MODE_NARRATIVE,
    ROLE_HUMAN_THROUGH_AI,
)
from genesis_v18_7_34_registration_binding_fresh_evidence_fix import (
    RegistrationRequestConflict,
)
from genesis_v18_7_36_validated_registration_binding import (
    ValidatedRegistrationLifecycleGateway,
)


class FakeWorld:
    def register_player(self, actor_id: str, *, display_name: str):
        return None

    def process_action(self, actor_id: str, action: str):
        raise AssertionError("narrative registration test must not process a turn")


class ValidatedRegistrationBindingTests(unittest.TestCase):
    @staticmethod
    def valid_kwargs(**overrides):
        values = dict(
            registration_request_id="REG-VALID",
            role=ROLE_HUMAN_THROUGH_AI,
            execution_mode=MODE_NARRATIVE,
            display_name="Mira",
            provider="test-provider",
            model="test-model",
            actor_id="mira",
        )
        values.update(overrides)
        return values

    def test_invalid_role_leaves_no_registration_binding(self):
        with tempfile.TemporaryDirectory() as td:
            gateway = ValidatedRegistrationLifecycleGateway(FakeWorld(), Path(td))
            with self.assertRaises(ValueError):
                gateway.register_session_saga(
                    **self.valid_kwargs(
                        registration_request_id="BAD-ROLE",
                        role="NOT_A_ROLE",
                    )
                )
            self.assertIsNone(gateway.registration_requests.get("BAD-ROLE"))

    def test_invalid_execution_mode_leaves_no_registration_binding(self):
        with tempfile.TemporaryDirectory() as td:
            gateway = ValidatedRegistrationLifecycleGateway(FakeWorld(), Path(td))
            with self.assertRaises(ValueError):
                gateway.register_session_saga(
                    **self.valid_kwargs(
                        registration_request_id="BAD-MODE",
                        execution_mode="NOT_A_MODE",
                    )
                )
            self.assertIsNone(gateway.registration_requests.get("BAD-MODE"))

    def test_missing_actor_leaves_no_registration_binding(self):
        with tempfile.TemporaryDirectory() as td:
            gateway = ValidatedRegistrationLifecycleGateway(FakeWorld(), Path(td))
            with self.assertRaises(ValueError):
                gateway.register_session_saga(
                    **self.valid_kwargs(
                        registration_request_id="BAD-ACTOR",
                        actor_id=None,
                    )
                )
            self.assertIsNone(gateway.registration_requests.get("BAD-ACTOR"))

    def test_empty_request_id_leaves_no_registration_binding(self):
        with tempfile.TemporaryDirectory() as td:
            gateway = ValidatedRegistrationLifecycleGateway(FakeWorld(), Path(td))
            with self.assertRaises(ValueError):
                gateway.register_session_saga(
                    **self.valid_kwargs(registration_request_id="   ")
                )
            self.assertIsNone(gateway.registration_requests.get(""))

    def test_valid_request_is_bound_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            gateway = ValidatedRegistrationLifecycleGateway(FakeWorld(), Path(td))
            first = gateway.register_session_saga(**self.valid_kwargs())
            second = gateway.register_session_saga(**self.valid_kwargs())
            binding = gateway.registration_requests.get("REG-VALID")
            self.assertIsNotNone(binding)
            self.assertEqual(first["session_id"], second["session_id"])
            self.assertEqual(binding.session_id, first["session_id"])

    def test_valid_request_changed_parameters_still_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            gateway = ValidatedRegistrationLifecycleGateway(FakeWorld(), Path(td))
            gateway.register_session_saga(**self.valid_kwargs())
            with self.assertRaises(RegistrationRequestConflict):
                gateway.register_session_saga(
                    **self.valid_kwargs(display_name="Changed")
                )

    def test_invalid_attempt_cannot_poison_later_corrected_request(self):
        with tempfile.TemporaryDirectory() as td:
            gateway = ValidatedRegistrationLifecycleGateway(FakeWorld(), Path(td))
            with self.assertRaises(ValueError):
                gateway.register_session_saga(
                    **self.valid_kwargs(
                        registration_request_id="RECOVERABLE-ID",
                        execution_mode="INVALID",
                    )
                )
            self.assertIsNone(gateway.registration_requests.get("RECOVERABLE-ID"))

            accepted = gateway.register_session_saga(
                **self.valid_kwargs(registration_request_id="RECOVERABLE-ID")
            )
            binding = gateway.registration_requests.get("RECOVERABLE-ID")
            self.assertEqual(binding.session_id, accepted["session_id"])


if __name__ == "__main__":
    unittest.main()
