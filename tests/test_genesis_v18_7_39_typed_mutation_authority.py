from __future__ import annotations

import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from genesis_v18_7_33_inflight_duplicate_reconciliation import (
    ReconciledPortableReceiptRuntimeAdapter,
)
from genesis_v18_7_39_typed_mutation_authority import (
    ControlledGenesisMutationFacade,
    TypedAuxiliaryMutationAdapter,
    TypedMutationCrashInjector,
    TypedMutationCrashPoint,
    TypedMutationError,
    TypedMutationOutcomeUndetermined,
    TypedMutationRequestConflict,
    TypedMutationRequestStore,
)
from genesis_v18_7_playable import PlayableGenesisV187
from genesis_v18_models import Realm, WorldResult


class CountingWorld:
    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.process_calls = 0
        self.exit_calls = 0
        self.name_calls = 0
        self.display_names = {}
        self.active = 0
        self.max_active = 0
        self.guard = threading.Lock()

    def _enter(self):
        with self.guard:
            self.active += 1
            self.max_active = max(self.max_active, self.active)

    def _leave(self):
        with self.guard:
            self.active -= 1

    def process_action(self, actor_id: str, action: str) -> WorldResult:
        self._enter()
        try:
            self.process_calls += 1
            if self.delay:
                time.sleep(self.delay)
            return WorldResult(
                status="OK",
                narrative=f"action:{action}",
                realm=Realm.REFLECTION,
                visible_grace=None,
                choices=[],
                trace_id=f"action-{self.process_calls}",
            )
        finally:
            self._leave()

    def force_exit(self, actor_id: str, *, reason: str = "system_interrupt") -> WorldResult:
        self._enter()
        try:
            self.exit_calls += 1
            if self.delay:
                time.sleep(self.delay)
            return WorldResult(
                status="EXIT",
                narrative=f"forced:{reason}",
                realm=Realm.REFLECTION,
                visible_grace=None,
                choices=[],
                trace_id=f"exit-{self.exit_calls}",
            )
        finally:
            self._leave()

    def set_display_name(self, actor_id: str, display_name: str) -> None:
        self._enter()
        try:
            self.name_calls += 1
            if self.delay:
                time.sleep(self.delay)
            self.display_names[actor_id] = display_name
        finally:
            self._leave()


class TypedForceExitTests(unittest.TestCase):
    def test_same_force_exit_request_replays_without_second_raw_exit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld()
            adapter = TypedAuxiliaryMutationAdapter(world, root)
            first = adapter.force_exit(
                client_id="cli",
                request_id="EXIT-1",
                actor_id="mira",
                reason="keyboard_interrupt",
            )
            second = adapter.force_exit(
                client_id="cli",
                request_id="EXIT-1",
                actor_id="mira",
                reason="keyboard_interrupt",
            )
            self.assertEqual(world.exit_calls, 1)
            self.assertEqual(first.to_dict(internal=True), second.to_dict(internal=True))
            state = adapter.request_state(client_id="cli", request_id="EXIT-1")
            self.assertEqual(state["state"], "SETTLED")
            self.assertTrue(state["full_result_receipt_persisted"])

    def test_same_force_exit_request_changed_reason_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld()
            adapter = TypedAuxiliaryMutationAdapter(world, root)
            adapter.force_exit(
                client_id="cli", request_id="EXIT-X", actor_id="mira", reason="eof"
            )
            with self.assertRaises(TypedMutationRequestConflict):
                adapter.force_exit(
                    client_id="cli",
                    request_id="EXIT-X",
                    actor_id="mira",
                    reason="keyboard_interrupt",
                )
            self.assertEqual(world.exit_calls, 1)

    def test_crash_after_raw_force_exit_before_receipt_blocks_second_exit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld()
            crashing = TypedAuxiliaryMutationAdapter(
                world,
                root,
                crash_injector=TypedMutationCrashInjector(
                    TypedMutationCrashPoint.AFTER_WORLD_BEFORE_RECEIPT
                ),
            )
            with self.assertRaises(TypedMutationError):
                crashing.force_exit(
                    client_id="cli",
                    request_id="EXIT-CRASH",
                    actor_id="mira",
                    reason="power_boundary",
                )
            self.assertEqual(world.exit_calls, 1)
            with self.assertRaises(TypedMutationOutcomeUndetermined):
                TypedAuxiliaryMutationAdapter(world, root).force_exit(
                    client_id="cli",
                    request_id="EXIT-CRASH",
                    actor_id="mira",
                    reason="power_boundary",
                )
            self.assertEqual(world.exit_calls, 1)


class TypedDisplayNameTests(unittest.TestCase):
    def test_same_name_request_replays_without_second_raw_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld()
            adapter = TypedAuxiliaryMutationAdapter(world, root)
            first = adapter.set_display_name(
                client_id="cli", request_id="NAME-1", actor_id="mira", display_name="Mira"
            )
            second = adapter.set_display_name(
                client_id="cli", request_id="NAME-1", actor_id="mira", display_name="Mira"
            )
            self.assertEqual(world.name_calls, 1)
            self.assertEqual(first, second)
            self.assertEqual(world.display_names["mira"], "Mira")

    def test_same_name_request_changed_name_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld()
            adapter = TypedAuxiliaryMutationAdapter(world, root)
            adapter.set_display_name(
                client_id="cli", request_id="NAME-X", actor_id="mira", display_name="Mira"
            )
            with self.assertRaises(TypedMutationRequestConflict):
                adapter.set_display_name(
                    client_id="cli", request_id="NAME-X", actor_id="mira", display_name="Other"
                )
            self.assertEqual(world.name_calls, 1)

    def test_request_id_cannot_change_mutation_kind(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld()
            adapter = TypedAuxiliaryMutationAdapter(world, root)
            adapter.set_display_name(
                client_id="cli", request_id="KIND-X", actor_id="mira", display_name="Mira"
            )
            with self.assertRaises(TypedMutationRequestConflict):
                adapter.force_exit(
                    client_id="cli", request_id="KIND-X", actor_id="mira", reason="eof"
                )
            self.assertEqual(world.exit_calls, 0)

    def test_real_playable_display_name_settles_and_replays(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = PlayableGenesisV187(root)
            adapter = TypedAuxiliaryMutationAdapter(world, root)
            first = adapter.set_display_name(
                client_id="cli",
                request_id="REAL-NAME",
                actor_id="mira",
                display_name="Mira",
            )
            second = adapter.set_display_name(
                client_id="cli",
                request_id="REAL-NAME",
                actor_id="mira",
                display_name="Mira",
            )
            self.assertEqual(first, second)
            self.assertEqual(world.public_state("mira")["display_name"], "Mira")


class SharedWorldLockTests(unittest.TestCase):
    def test_process_action_and_display_name_share_one_local_world_lock(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld(delay=0.08)
            actions = ReconciledPortableReceiptRuntimeAdapter(world, root)
            auxiliary = TypedAuxiliaryMutationAdapter(world, root)
            start = threading.Barrier(2)

            def action_call():
                start.wait(timeout=5)
                return actions.execute(
                    client_id="cli",
                    request_id="ACTION-1",
                    actor_id="mira",
                    action="observe",
                )

            def name_call():
                start.wait(timeout=5)
                return auxiliary.set_display_name(
                    client_id="cli",
                    request_id="NAME-LOCK",
                    actor_id="mira",
                    display_name="Mira",
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(action_call), pool.submit(name_call)]
                for future in futures:
                    future.result(timeout=10)
            self.assertEqual(world.process_calls, 1)
            self.assertEqual(world.name_calls, 1)
            self.assertEqual(world.max_active, 1)

    def test_two_active_duplicate_force_exit_callers_converge_to_one_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            world = CountingWorld(delay=0.08)
            a = TypedAuxiliaryMutationAdapter(world, root)
            b = TypedAuxiliaryMutationAdapter(world, root)
            start = threading.Barrier(2)

            def run(adapter):
                start.wait(timeout=5)
                return adapter.force_exit(
                    client_id="cli",
                    request_id="EXIT-DUP",
                    actor_id="mira",
                    reason="eof",
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [f.result(timeout=10) for f in (pool.submit(run, a), pool.submit(run, b))]
            self.assertEqual(world.exit_calls, 1)
            self.assertEqual(results[0].to_dict(internal=True), results[1].to_dict(internal=True))


class ControlledFacadeTests(unittest.TestCase):
    def test_facade_constructs_cooperating_controlled_paths(self):
        with tempfile.TemporaryDirectory() as td:
            facade = ControlledGenesisMutationFacade(Path(td))
            facade.set_display_name(
                client_id="facade",
                request_id="NAME-FACADE",
                actor_id="mira",
                display_name="Mira",
            )
            result = facade.process_action(
                client_id="facade",
                request_id="ACTION-FACADE",
                actor_id="mira",
                action="Осмотреться",
            )
            self.assertIsNotNone(result)
            exit_result = facade.force_exit(
                client_id="facade",
                request_id="EXIT-FACADE",
                actor_id="mira",
                reason="test",
            )
            self.assertEqual(exit_result.status, "EXIT")

    def test_store_releases_sqlite_handles_for_immediate_cleanup(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        store = TypedMutationRequestStore(root / "typed.sqlite3")
        store.bind(
            client_id="c",
            request_id="r",
            mutation_kind="SET_DISPLAY_NAME",
            actor_id="mira",
            payload={"display_name": "Mira"},
        )
        temp.cleanup()
        self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
