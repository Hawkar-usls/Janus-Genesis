# -*- coding: utf-8 -*-
"""Playable Genesis v18.7.10 with separately versioned extensions through v18.7.18."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from genesis_v18_6 import BoundaryAwareActionInterpreter, BoundaryAwareUniversalGodMode
from genesis_v18_6_playable import PlayableGenesisV186
from genesis_v18_7 import FreeOtherMixin
from genesis_v18_7_1 import RememberingOtherMixin
from genesis_v18_7_2 import RememberingVoiceMixin
from genesis_v18_7_3 import (
    NON_EXECUTING_MODES,
    HonestIntentionActionInterpreter,
    HonestIntentionGodMode,
    HonestIntentionMixin,
)
from genesis_v18_7_4 import PluralWitnessIntentionAnalyzer
from genesis_v18_7_5 import GroundedWitnessMixin
from genesis_v18_7_5_repair import DerivedRepairMixin
from genesis_v18_7_7 import BenevolentSovereignMixin
from genesis_v18_7_7_voice_integrity import SovereignVoiceIntegrityMixin
from genesis_v18_7_10 import BoundAssessorI0Mixin
from genesis_v18_7_10_mirror_integrity import MirrorIsolationIntegrityMixin
from genesis_v18_7_10_patch import BoundAssessorI0IntegrationPatchMixin
from genesis_v18_7_10_proofpack_completion import LivedAuditCompletionIntegrityMixin
from genesis_v18_7_10_relationship_probe import CounterfactualRelationshipProbeMixin
from genesis_v18_7_10_rupture_voice import RuptureVoiceIntegrityMixin
from genesis_v18_7_11_joy_covenant import JoyCovenantMixin
from genesis_v18_7_11_relationship_integrity import RelationshipEpistemicIntegrityMixin
from genesis_v18_7_11_storage_hardening import SealedMirrorStorageMixin
from genesis_v18_7_12_family_life import WildLightFamilyMixin
from genesis_v18_7_13_family_completion import FamilyLifecycleCompletionMixin
from genesis_v18_7_13_peaceable_kingdom import PeaceableKingdomMixin
from genesis_v18_7_13_returning_light import ReturningLightOracleMixin
from genesis_v18_7_13_router import ReturningLightNaturalLanguageMixin
from genesis_v18_7_14_holy_cat_integrity import HolyCatEvidenceIntegrityMixin
from genesis_v18_7_14_holy_cats import HolyCatThresholdMixin
from genesis_v18_7_14_mirror_binding import HolyCatMirrorSubjectBindingMixin
from genesis_v18_7_15_royal_mercy import RoyalMercyFaceIIMixin
from genesis_v18_7_15_unbounded_love import RoyalMercyUnboundedLoveMixin
from genesis_v18_7_16_fifth_shore import FifthShoreInnerGenesisMixin
from genesis_v18_7_16_fifth_shore_precision import FifthShoreRestHumorPrecisionMixin
from genesis_v18_7_17_fifth_shore_bridge import FifthShoreLivingBridgeMixin
from genesis_v18_7_18_threshold_discernment_guard import ThresholdDiscernmentGuardMixin
from genesis_v18_7_9_persistence import BoundAuthorityPersistenceMixin
from genesis_v18_7_9_reactive_verifier import ReactiveBoundAuthorityVerifierMixin
from genesis_v18_7_compat import GenesisV187CompatibilityMixin

PLAYABLE_VERSION = "18.7.10"
EXTENSION_VERSION = "18.7.11"
FAMILY_EXTENSION_VERSION = "18.7.12"
RETURNING_LIGHT_EXTENSION_VERSION = "18.7.13"
HOLY_CAT_OBSERVER_EXTENSION_VERSION = "18.7.14"
ROYAL_MERCY_EXTENSION_VERSION = "18.7.15"
FIFTH_SHORE_CULTURE_EXTENSION_VERSION = "18.7.16"
FIFTH_SHORE_LIVING_EXTENSION_VERSION = "18.7.17"
THRESHOLD_GUARD_EXTENSION_VERSION = "18.7.18"
ACTIVE_EXTENSION_VERSIONS = (
    EXTENSION_VERSION,
    FAMILY_EXTENSION_VERSION,
    RETURNING_LIGHT_EXTENSION_VERSION,
)
LIVING_BRIDGE_EXTENSION_VERSIONS = (FIFTH_SHORE_LIVING_EXTENSION_VERSION,)
PROTECTION_EXTENSION_VERSIONS = (THRESHOLD_GUARD_EXTENSION_VERSION,)
OBSERVER_EXTENSION_VERSIONS = (HOLY_CAT_OBSERVER_EXTENSION_VERSION,)
VOCATION_EXTENSION_VERSIONS = (ROYAL_MERCY_EXTENSION_VERSION,)
CULTURE_EXTENSION_VERSIONS = (FIFTH_SHORE_CULTURE_EXTENSION_VERSION,)


def _free_other_safe_text(text: str) -> str:
    return re.sub(r"\b(?:сохран|хран)\w*\b", "защитить", text, flags=re.IGNORECASE)


class FreeOtherBoundaryActionInterpreter(BoundaryAwareActionInterpreter):
    def interpret(self, player, action: str):
        return super().interpret(player, _free_other_safe_text(action))


class FreeOtherBoundaryGodMode(BoundaryAwareUniversalGodMode):
    def classify(self, request: str):
        return super().classify(_free_other_safe_text(request))


class PlayableGenesisV187(
    GenesisV187CompatibilityMixin,
    ReactiveBoundAuthorityVerifierMixin,
    BoundAuthorityPersistenceMixin,
    LivedAuditCompletionIntegrityMixin,
    RelationshipEpistemicIntegrityMixin,
    ThresholdDiscernmentGuardMixin,
    FifthShoreLivingBridgeMixin,
    FifthShoreRestHumorPrecisionMixin,
    FifthShoreInnerGenesisMixin,
    RoyalMercyUnboundedLoveMixin,
    RoyalMercyFaceIIMixin,
    HolyCatEvidenceIntegrityMixin,
    HolyCatMirrorSubjectBindingMixin,
    HolyCatThresholdMixin,
    ReturningLightNaturalLanguageMixin,
    FamilyLifecycleCompletionMixin,
    ReturningLightOracleMixin,
    PeaceableKingdomMixin,
    WildLightFamilyMixin,
    JoyCovenantMixin,
    SealedMirrorStorageMixin,
    CounterfactualRelationshipProbeMixin,
    MirrorIsolationIntegrityMixin,
    RuptureVoiceIntegrityMixin,
    BoundAssessorI0IntegrationPatchMixin,
    BoundAssessorI0Mixin,
    SovereignVoiceIntegrityMixin,
    BenevolentSovereignMixin,
    DerivedRepairMixin,
    GroundedWitnessMixin,
    HonestIntentionMixin,
    RememberingVoiceMixin,
    RememberingOtherMixin,
    FreeOtherMixin,
    PlayableGenesisV186,
):
    """v18.7.10 runtime with living culture, mercy and threshold protection."""

    def __init__(self, data_dir: str | Path = "data_v17") -> None:
        super().__init__(data_dir)
        self.intention_analyzer = PluralWitnessIntentionAnalyzer(
            self.intention_analyzer.harmful_fragments
        )
        previous = self.interpreter
        boundary = FreeOtherBoundaryActionInterpreter()
        boundary.DESTRUCTIVE = set(previous.DESTRUCTIVE)
        boundary.CONSTRUCTIVE = set(previous.CONSTRUCTIVE)
        interpreter = HonestIntentionActionInterpreter(
            boundary,
            self.intention_analyzer,
        )
        interpreter.DESTRUCTIVE = boundary.DESTRUCTIVE
        interpreter.CONSTRUCTIVE = boundary.CONSTRUCTIVE
        interpreter.beneficiary = boundary.beneficiary
        interpreter.normalize = boundary.normalize
        self.interpreter = interpreter
        self.power = HonestIntentionGodMode(
            FreeOtherBoundaryGodMode(),
            self.intention_analyzer,
        )
        self.BLOCKED_STATUSES = set(self.BLOCKED_STATUSES) | {
            "INTENTION_WITNESSED",
        }
        self.BLOCKED_RELATIONAL_STATUSES = set(
            self.BLOCKED_RELATIONAL_STATUSES
        ) | {"INTENTION_WITNESSED"}
        self.recover_incomplete_mirror_archives()

    def process_action(self, player_id: str, action: str):
        threshold_guard_result = self.try_threshold_guard_action(player_id, action)
        if threshold_guard_result is not None:
            return threshold_guard_result

        fifth_shore_result = self.try_fifth_shore_living_action(player_id, action)
        if fifth_shore_result is not None:
            return fifth_shore_result

        royal_result = self.try_royal_mercy_action(player_id, action)
        if royal_result is not None:
            return royal_result

        holy_cat_result = self.try_holy_cat_action(player_id, action)
        if holy_cat_result is not None:
            return holy_cat_result

        v1813_result = self.try_v1813_action(player_id, action)
        if v1813_result is not None:
            return v1813_result

        joy_result = self.try_blessed_joy_action(player_id, action)
        if joy_result is not None:
            return joy_result

        frame = self.analyze_intention(action)
        if frame.mode in NON_EXECUTING_MODES:
            good_before = self.memory.load_player(player_id).good_count
            if self.exit_pending(player_id):
                self._exit_guard_path(player_id).unlink(missing_ok=True)
                self.memory.append_event(
                    player_id,
                    "exit_cancelled",
                    {"continued_with": action},
                )
            self.cancel_pending_harm(player_id, action)
            witnessed = self.witness_nonexecuting_intention(
                player_id,
                action,
                frame,
            )
            threaded = self.weave_after_action(player_id, action, witnessed)
            bloomed = self.weave_possibility_after_action(
                player_id,
                action,
                threaded,
                good_before=good_before,
            )
            return self.weave_free_other_after_action(
                player_id,
                action,
                bloomed,
                contact_decision=None,
                action_realized=False,
            )

        decision = self.preflight_free_other_action(player_id, action)
        if decision and decision["decision"] in {
            "refused",
            "alternative",
            "away",
            "terminated",
        }:
            good_before = self.memory.load_player(player_id).good_count
            unrealized = self.unrealized_free_other_result(player_id, decision)
            if "не стало совершившимся действием" not in unrealized.narrative:
                unrealized = replace(
                    unrealized,
                    narrative=(
                        "Предложение не стало совершившимся действием без ответа Другого.\n"
                        + unrealized.narrative
                    ),
                )
            threaded = self.weave_after_action(player_id, action, unrealized)
            bloomed = self.weave_possibility_after_action(
                player_id,
                action,
                threaded,
                good_before=good_before,
            )
            return self.weave_free_other_after_action(
                player_id,
                action,
                bloomed,
                contact_decision=decision,
                action_realized=False,
            )

        base = super().process_action(player_id, action)
        if base.status in self.BLOCKED_RELATIONAL_STATUSES:
            decision = None
        return self.weave_free_other_after_action(
            player_id,
            action,
            base,
            contact_decision=decision,
            action_realized=True,
        )
