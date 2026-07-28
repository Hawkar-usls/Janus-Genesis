# -*- coding: utf-8 -*-
"""Witness-proof integrity for Genesis v18.7.7.

This is a local/reference identity boundary, not a claim that arbitrary proof
strings provide real-world personhood verification. A production network must
bind the proof to its authenticated identity provider.
"""
from __future__ import annotations

import hashlib
from typing import Any

from genesis_v18_7_7 import BenevolentSovereignMixin

__version__ = "18.7.7"


class SovereignVoiceIntegrityMixin:
    """Prevent one bound proof from being presented as several witness voices."""

    @staticmethod
    def _default_plural_store() -> dict[str, Any]:
        store = BenevolentSovereignMixin._default_plural_store()
        store["invariants"].update(
            {
                "one_bound_proof_maps_to_one_reader_voice": True,
                "local_proof_is_not_real_world_identity_claim": True,
                "production_voice_requires_authenticated_provider": True,
            }
        )
        return store

    def register_witness_voice(
        self,
        reader_id: str,
        *,
        proof: str,
        consent: bool,
        identity_provider: str = "local_reference",
    ) -> dict[str, Any]:
        reader_id = str(reader_id).strip()
        proof = str(proof)
        identity_provider = str(identity_provider).strip() or "local_reference"
        if not reader_id or len(proof) < 8:
            raise ValueError("reader_id and a non-trivial proof are required")
        proof_sha256 = hashlib.sha256(proof.encode("utf-8")).hexdigest()
        store = self._plural_store()
        for existing_id, entry in store.get("voice_registry", {}).items():
            if existing_id != reader_id and entry.get("proof_sha256") == proof_sha256:
                raise ValueError("one bound proof cannot register multiple reader voices")
        result = super().register_witness_voice(
            reader_id,
            proof=proof,
            consent=consent,
        )
        store = self._plural_store()
        entry = store["voice_registry"][reader_id]
        entry["identity_provider"] = identity_provider
        entry["verification_status"] = "reference_proof_bound"
        entry["real_world_identity_claimed"] = False
        entry["production_authentication_required"] = True
        self._write_json(self.plural_witness_path, store)
        return dict(entry)
