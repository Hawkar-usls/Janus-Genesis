# -*- coding: utf-8 -*-
"""Privacy-safe subject binding for Holy Cat counterfactual archives."""
from __future__ import annotations

import copy
import re
from typing import Any

from genesis_v18_7_10 import sha256_canonical

_HOLY_CAT_LABEL = re.compile(r"\Aholy-cat-face:([0-9a-f]{24})\Z")


class HolyCatMirrorSubjectBindingMixin:
    """Persist only a namespaced hash prefix, never a raw mirror label."""

    def archive_counterfactual_mirror(
        self,
        mirror: Any,
        manifest: dict[str, Any],
        *,
        metrics: dict[str, Any],
        remove_working_copy: bool = True,
    ) -> dict[str, Any]:
        label = str(manifest.get("label", ""))
        match = _HOLY_CAT_LABEL.fullmatch(label)
        if label.startswith("holy-cat-face:") and match is None:
            raise ValueError("HOLY_CAT_MIRROR_LABEL_MALFORMED")
        if match is not None:
            branch_manifest = mirror._counterfactual_manifest()
            if branch_manifest.get("label") != label:
                raise RuntimeError("HOLY_CAT_MIRROR_LABEL_CHANGED_AFTER_FORK")

        archive = super().archive_counterfactual_mirror(
            mirror,
            manifest,
            metrics=metrics,
            remove_working_copy=remove_working_copy,
        )
        archive["raw_mirror_label_archived"] = False
        archive["privacy_safe_subject_binding"] = None
        archive["privacy_safe_subject_binding_sha256"] = None

        if match is not None:
            binding = {
                "namespace": "holy-cat-face",
                "subject_hash_prefix": match.group(1),
            }
            archive["privacy_safe_subject_binding"] = binding
            archive["privacy_safe_subject_binding_sha256"] = sha256_canonical(
                binding
            )

        store = self._i0_store()
        stored = store.setdefault("mirror_archives", {}).get(
            str(manifest["mirror_id"])
        )
        if not isinstance(stored, dict):
            raise RuntimeError("MIRROR_ARCHIVE_MISSING_AFTER_SEAL")
        stored.update(
            {
                "raw_mirror_label_archived": False,
                "privacy_safe_subject_binding": copy.deepcopy(
                    archive["privacy_safe_subject_binding"]
                ),
                "privacy_safe_subject_binding_sha256": archive[
                    "privacy_safe_subject_binding_sha256"
                ],
            }
        )
        self._write_json(self.i0_audit_path, store)
        return copy.deepcopy(archive)
