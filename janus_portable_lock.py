# -*- coding: utf-8 -*-
"""Small cross-platform advisory process lock used by JANUS local control files.

POSIX uses flock shared/exclusive semantics. Windows msvcrt does not expose a
shared reader lock, so ``shared()`` intentionally becomes an exclusive lock on
Windows. That is more conservative: it reduces concurrency but does not weaken
serialization.

This is a same-host/shared-filesystem coordination primitive. It is not a
multi-host consensus or lease protocol.
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


class PortableProcessLock:
    """Advisory one-byte sidecar lock with POSIX and Windows implementations."""

    def __init__(self, path: str | os.PathLike[str], *, poll_seconds: float = 0.01) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.poll_seconds = max(float(poll_seconds), 0.001)
        self._thread_lock = threading.RLock()
        # msvcrt.locking locks a byte range. Keep one real byte in the sidecar
        # rather than modifying the protected data file itself.
        if not self.path.exists() or self.path.stat().st_size < 1:
            with self.path.open("ab") as handle:
                if handle.tell() < 1:
                    handle.write(b"\0")
                    handle.flush()
                    os.fsync(handle.fileno())

    @staticmethod
    def _seek_lock_byte(handle) -> None:
        handle.seek(0)

    def _acquire_handle(self, handle, *, shared: bool, blocking: bool) -> None:
        self._seek_lock_byte(handle)
        if os.name == "nt":
            # Windows' stdlib primitive has no shared-reader equivalent here;
            # shared=True is conservatively treated as exclusive.
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    if not blocking:
                        raise BlockingIOError("portable process lock busy")
                    time.sleep(self.poll_seconds)
        else:
            operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            if not blocking:
                operation |= fcntl.LOCK_NB
            fcntl.flock(handle.fileno(), operation)

    def _release_handle(self, handle) -> None:
        self._seek_lock_byte(handle)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @contextlib.contextmanager
    def _held(self, *, shared: bool) -> Iterator[None]:
        with self._thread_lock:
            with self.path.open("r+b") as handle:
                self._acquire_handle(handle, shared=shared, blocking=True)
                try:
                    yield
                finally:
                    self._release_handle(handle)

    def exclusive(self):
        return self._held(shared=False)

    def shared(self):
        return self._held(shared=True)

    def try_acquire(self, *, shared: bool = False) -> bool:
        with self.path.open("r+b") as handle:
            try:
                self._acquire_handle(handle, shared=shared, blocking=False)
            except BlockingIOError:
                return False
            else:
                self._release_handle(handle)
                return True

    @property
    def semantics(self) -> str:
        if os.name == "nt":
            return "WINDOWS_EXCLUSIVE_BYTE_RANGE_LOCK_SHARED_REQUESTS_SERIALIZED"
        return "POSIX_FLOCK_SHARED_EXCLUSIVE"


__all__ = ["PortableProcessLock"]
