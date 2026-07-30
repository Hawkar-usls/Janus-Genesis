# -*- coding: utf-8 -*-
"""Fail-closed evidence binding for the Holy Cat threshold."""
from __future__ import annotations

from typing import Any

from genesis_v18_7_10 import sha256_canonical
from genesis_v18_7_14_holy_cats import HOLY_CAT_COVENANT_SHA256


class HolyCatEvidenceIntegrityMixin:
    """Require current canonical truth and hash-bound mirror metrics."""

    def holy_cat_witness_between_worlds(
        self,
        subject_id: str,
        *,
        canonical_witness: dict[str, Any],
        mirror_archive: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in canonical_witness.items()
            if key != "witness_sha256"
        }
        if payload.get("covenant_sha256") != HOLY_CAT_COVENANT_SHA256:
            raise RuntimeError("HOLY_CAT_CANONICAL_WITNESS_COVENANT_MISMATCH")
        canonical_metrics = self._validate_face_metrics(
            dict(payload.get("metrics", {}))
        )
        authoritative_metrics = self.holy_cat_face_witness_metrics(
            str(subject_id)
        )
        if canonical_metrics != authoritative_metrics:
            raise RuntimeError("HOLY_CAT_CANONICAL_METRICS_NOT_AUTHORITATIVE")
        mirror_metrics = self._validate_face_metrics(
            dict(mirror_archive.get("metrics", {}))
        )
        if mirror_archive.get("metrics_sha256") != sha256_canonical(
            mirror_metrics
        ):
            raise RuntimeError("HOLY_CAT_MIRROR_METRICS_HASH_MISMATCH")
        return super().holy_cat_witness_between_worlds(
            str(subject_id),
            canonical_witness=canonical_witness,
            mirror_archive=mirror_archive,
        )
