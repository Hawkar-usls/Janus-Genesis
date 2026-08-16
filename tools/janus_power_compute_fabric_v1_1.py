# -*- coding: utf-8 -*-
"""JANUS POWER v1.1 additive hardening over the frozen v1 component.

The v1 source remains unchanged and keeps its exact-head component PASS.
This successor closes two semantic edges:

1. a cooperative local deadline is a TIMEOUT, not a generic FAILED result;
2. memory telemetry supports both the historical ``remember(source, content)``
   contract and the user-seed ``remember(tag, content)`` contract without
   treating an arbitrary runtime TypeError as an API-discovery signal.
"""
from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any

from tools.janus_power_compute_fabric import (
    ComputeCancelled,
    JanusPowerCore as JanusPowerCoreV1,
)


class JanusPowerCoreV11(JanusPowerCoreV1):
    """Additive v1.1 successor; all v1 capability/effect boundaries remain."""

    async def _cooperate(self, request, deadline: float) -> None:
        if request.cancel_requested:
            raise ComputeCancelled("TASK_CANCEL_REQUESTED")
        if time.monotonic() > deadline:
            # _process_request in v1 already classifies asyncio.TimeoutError as
            # TaskStatus.TIMEOUT. Raising that exact semantic signal avoids a
            # scheduler-dependent FAILED-vs-TIMEOUT race at the local deadline.
            raise asyncio.TimeoutError("COOPERATIVE_DEADLINE_EXCEEDED")
        await asyncio.sleep(0)

    @staticmethod
    def _memory_call_kwargs(remember: Any, event: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve the declared memory API before calling it.

        We inspect the callable signature rather than doing ``try source=...``
        followed by a TypeError fallback. The latter could accidentally call a
        memory backend twice when the first call accepted ``source`` but raised
        TypeError *inside* its own implementation.
        """
        try:
            signature = inspect.signature(remember)
        except (TypeError, ValueError):
            return None

        parameters = signature.parameters
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if "content" not in parameters and not accepts_kwargs:
            return None
        if "source" in parameters or accepts_kwargs:
            return {"source": "JANUS-POWER", "content": event}
        if "tag" in parameters:
            return {"tag": "JANUS-POWER", "content": event}
        return None

    async def _remember_event(self, event: dict[str, Any]) -> None:
        memory = getattr(self.kernel, "memory", None) if self.kernel is not None else None
        remember = getattr(memory, "remember", None)
        if not callable(remember):
            return

        kwargs = self._memory_call_kwargs(remember, event)
        if kwargs is None:
            task = self.tasks.get(str(event.get("task_id")))
            if task is not None and event.get("event") == "COMPUTE_TERMINAL":
                task.performance_metrics["memory_log_error"] = "UNSUPPORTED_MEMORY_API"
            return

        try:
            value = remember(**kwargs)
            if inspect.isawaitable(value):
                await value
        except Exception as exc:
            # Telemetry remains non-authoritative: compute status/result does not
            # change because a memory backend failed.
            if event.get("event") == "COMPUTE_TERMINAL":
                task = self.tasks.get(str(event.get("task_id")))
                if task is not None:
                    task.performance_metrics["memory_log_error"] = type(exc).__name__


async def run(kernel: Any) -> JanusPowerCoreV11:
    core = JanusPowerCoreV11(kernel)
    await core.start()
    kernel.power = core
    return core
