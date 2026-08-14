# -*- coding: utf-8 -*-
"""JANUS portable local lock v2 — process-global + OS-level serialization.

v1 used one ``threading.RLock`` per Python lock object. That was insufficient as
proof that two distinct lock objects in the same Windows process serialize each
other, because the Windows byte-range primitive is an OS/process boundary and
must not be treated as a substitute for an explicit in-process lock domain.

v2 therefore has two independent layers:
1. one process-global ``RLock`` for every canonical lock-file path;
2. one OS advisory lock on a one-byte sidecar for cross-process coordination.

On Windows a requested shared lock is conservatively serialized as exclusive.
This reduces concurrency rather than weakening safety. The primitive remains
same-host/shared-filesystem coordination. It is not multi-host consensus.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path
from typing import Iterator

if os.name == "nt":
    import msvcrt  # type: ignore[attr-defined]
else:
    import fcntl  # type: ignore[import-not-found]

PORTABLE_LOCK_V2_VERSION = "2.0"

_REGISTRY_GUARD = threading.RLock()
_PATH_LOCKS: dict[str, threading.RLock] = {}


def _canonical_lock_key(path: Path) -> str:
    resolved = str(path.resolve(strict=False))
    return os.path.normcase(resolved) if os.name == "nt" else resolved


def _process_lock_for(path: Path) -> threading.RLock:
    key = _canonical_lock_key(path)
    with _REGISTRY_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


class PortableProcessLockV2:
    """Two-layer advisory lock: process-global path lock + OS sidecar lock."""

    def __init__(self, path: str | os.PathLike[str], *, poll_seconds: float = 0.01) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.poll_seconds = max(float(poll_seconds), 0.001)
        self._process_lock = _process_lock_for(self.path)
        # Initialization itself must share the process path lock so two local
        # objects cannot race creation/truncation of the one-byte sidecar.
        with self._process_lock:
            if not self.path.exists() or self.path.stat().st_size < 1:
                with self.path.open("ab") as handle:
                    if handle.tell() < 1:
                        handle.write(b"\0")
                        handle.flush()
                        os.fsync(handle.fileno())

    @staticmethod
    def _seek_lock_byte(handle) -> None:
        handle.seek(0)

    def _acquire_os(self, handle, *, shared: bool, blocking: bool) -> None:
        self._seek_lock_byte(handle)
        if os.name == "nt":
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    return
                except OSError as exc:
                    if not blocking:
                        raise BlockingIOError("portable process lock busy") from exc
                    time.sleep(self.poll_seconds)
        else:
            operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            if not blocking:
                operation |= fcntl.LOCK_NB
            fcntl.flock(handle.fileno(), operation)

    def _release_os(self, handle) -> None:
        self._seek_lock_byte(handle)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @contextlib.contextmanager
    def _held(self, *, shared: bool) -> Iterator[None]:
        # The process lock is acquired before the OS lock everywhere, giving a
        # fixed lock order and preventing same-process cross-instance overlap.
        with self._process_lock:
            with self.path.open("r+b") as handle:
                self._acquire_os(handle, shared=shared, blocking=True)
                try:
                    yield
                finally:
                    self._release_os(handle)

    def exclusive(self):
        return self._held(shared=False)

    def shared(self):
        return self._held(shared=True)

    def try_acquire(self, *, shared: bool = False) -> bool:
        if not self._process_lock.acquire(blocking=False):
            return False
        try:
            with self.path.open("r+b") as handle:
                try:
                    self._acquire_os(handle, shared=shared, blocking=False)
                except BlockingIOError:
                    return False
                else:
                    self._release_os(handle)
                    return True
        finally:
            self._process_lock.release()

    @property
    def semantics(self) -> str:
        if os.name == "nt":
            return "PROCESS_GLOBAL_PATH_RLOCK_PLUS_WINDOWS_EXCLUSIVE_BYTE_RANGE_LOCK"
        return "PROCESS_GLOBAL_PATH_RLOCK_PLUS_POSIX_FLOCK_SHARED_EXCLUSIVE"


__all__ = ["PORTABLE_LOCK_V2_VERSION", "PortableProcessLockV2"]
