# -*- coding: utf-8 -*-
"""JANUS Genesis v18.7.35 — Windows-safe final-file fsync descendant.

The v18.7.34 cross-platform run preserved another real portability failure:
Linux accepted ``os.fsync`` on a final file reopened read-only, while Windows
raised ``OSError: [Errno 9] Bad file descriptor``. v18.7.35 changes only that
resource contract: after atomic same-directory replacement the final path is
opened through an explicit read/write OS descriptor and fsynced before close.

POSIX additionally fsyncs the containing directory when supported. Windows still
makes no claim that Python exposes an equivalent directory-entry fsync; its claim
is limited to unique same-directory temp, temp fsync, atomic same-volume replace,
and final-file fsync through a writable descriptor.

This is a descendant correction. It does not relabel run 31828864663 as passing.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from genesis_v18_7_32_durable_session_key_lifecycle import DurableWriteReceipt
from genesis_v18_7_34_registration_binding_fresh_evidence_fix import (
    BoundRegistrationLifecycleGateway,
)

WINDOWS_SAFE_DURABLE_WRITER_VERSION = "18.7.35"
WINDOWS_SAFE_DURABLE_WRITER_SCHEMA = "janus.genesis.windows_safe_durable_writer.v1"


class WindowsSafeDurableJsonWriter:
    """Crash-conscious JSON replacement with explicit final descriptor ownership."""

    def write(self, path: str | Path, value: Mapping[str, Any]) -> DurableWriteReceipt:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        directory_synced = False
        directory_supported = os.name != "nt"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{target.name}.",
                suffix=".tmp",
                dir=target.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_path, target)
            temp_path = None

            # Windows FlushFileBuffers via Python's os.fsync requires a handle
            # compatible with writes. Use an explicitly owned read/write fd on
            # every platform so the contract is identical and unambiguous.
            final_fd = os.open(str(target), os.O_RDWR)
            try:
                os.fsync(final_fd)
            finally:
                os.close(final_fd)

            if directory_supported:
                flags = os.O_RDONLY
                if hasattr(os, "O_DIRECTORY"):
                    flags |= os.O_DIRECTORY
                dir_fd = os.open(str(target.parent), flags)
                try:
                    os.fsync(dir_fd)
                    directory_synced = True
                finally:
                    os.close(dir_fd)

            return DurableWriteReceipt(
                path=str(target),
                temp_was_unique=True,
                temp_file_fsynced=True,
                replaced=True,
                final_file_fsynced=True,
                directory_fsynced=directory_synced,
                directory_fsync_supported=directory_supported,
            )
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass


class WindowsSafeBoundRegistrationLifecycleGateway(BoundRegistrationLifecycleGateway):
    """v18.7.34 request binding with the v18.7.35 durable writer."""

    def __init__(self, world, data_dir, **kwargs) -> None:
        super().__init__(world, data_dir, **kwargs)
        self.durable_writer = WindowsSafeDurableJsonWriter()


__all__ = [
    "WINDOWS_SAFE_DURABLE_WRITER_VERSION",
    "WINDOWS_SAFE_DURABLE_WRITER_SCHEMA",
    "WindowsSafeDurableJsonWriter",
    "WindowsSafeBoundRegistrationLifecycleGateway",
]
