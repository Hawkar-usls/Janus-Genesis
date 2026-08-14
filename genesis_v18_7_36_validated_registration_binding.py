# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.36 — validate registration before durable request binding.

The v6.6 audit found that v18.7.34/v18.7.35 could durably bind a
``registration_request_id`` before the parent saga rejected an unsupported role
or execution mode. That allowed an invalid attempt to poison a logical request
identity.

v18.7.36 makes validation an explicit pre-binding gate. No durable registration
request row is created until the complete parent-facing registration contract is
known to be syntactically admissible.

This descendant does not claim that syntactic admission proves actor identity,
provider identity, genealogy, or cross-store atomicity. It closes only the
request-poisoning boundary for the validated descendant path.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from genesis_v18_7_19_ai_link_play import (
    ROLE_INDEPENDENT_AI,
    SUPPORTED_EXECUTION_MODES,
    SUPPORTED_ROLES,
    _canonical_actor_id,
)
from genesis_v18_7_35_windows_safe_durable_writer import (
    WindowsSafeBoundRegistrationLifecycleGateway,
)

VALIDATED_REGISTRATION_BINDING_VERSION = "18.7.36"
VALIDATED_REGISTRATION_BINDING_SCHEMA = "janus.genesis.validated_registration_binding.v1"


class ValidatedRegistrationLifecycleGateway(WindowsSafeBoundRegistrationLifecycleGateway):
    """Run the parent's syntactic registration admission before durable binding."""

    @staticmethod
    def _prevalidate_registration(
        *,
        registration_request_id: str,
        role: str,
        execution_mode: str,
        display_name: str,
        provider: str,
        model: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        request_id = str(registration_request_id).strip()
        if not request_id or len(request_id) > 240:
            raise ValueError("REGISTRATION_REQUEST_ID_REQUIRED")

        role_value = str(role).strip().upper()
        execution_mode_value = str(execution_mode).strip().upper()
        if role_value not in SUPPORTED_ROLES:
            raise ValueError(f"AI_LINK_UNSUPPORTED_ROLE:{role_value}")
        if execution_mode_value not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(
                f"AI_LINK_UNSUPPORTED_EXECUTION_MODE:{execution_mode_value}"
            )

        # Mirror the parent normalization so anything that can fail before the
        # request binding is exercised here first.
        display_value = str(display_name).strip()[:120] or "Genesis Visitor"
        provider_value = str(provider).strip()[:120] or "unknown-provider"
        model_value = str(model).strip()[:160] or "unknown-model"

        canonical_actor: str | None
        if role_value == ROLE_INDEPENDENT_AI:
            canonical_actor = None
        else:
            if actor_id is None or not str(actor_id).strip():
                raise ValueError("AI_LINK_HUMAN_ACTOR_ID_REQUIRED")
            canonical_actor = _canonical_actor_id(str(actor_id))

        return {
            "registration_request_id": request_id,
            "role": role_value,
            "execution_mode": execution_mode_value,
            "display_name": display_value,
            "provider": provider_value,
            "model": model_value,
            "actor_id": canonical_actor,
        }

    def register_session_saga(
        self,
        *,
        registration_request_id: str,
        role: str,
        execution_mode: str,
        display_name: str,
        provider: str,
        model: str,
        actor_id: str | None = None,
    ):
        # The returned normalized values are deliberately passed into the parent.
        # Thus the exact values admitted are the values durably bound.
        normalized = self._prevalidate_registration(
            registration_request_id=registration_request_id,
            role=role,
            execution_mode=execution_mode,
            display_name=display_name,
            provider=provider,
            model=model,
            actor_id=actor_id,
        )
        return super().register_session_saga(**normalized)


__all__ = [
    "VALIDATED_REGISTRATION_BINDING_VERSION",
    "VALIDATED_REGISTRATION_BINDING_SCHEMA",
    "ValidatedRegistrationLifecycleGateway",
]
