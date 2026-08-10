# -*- coding: utf-8 -*-
"""Resilient entrypoint for the Round-2 Ollama experiment.

The first Round-2 CI attempt observed a transient Ollama llama-server SIGSEGV
(HTTP 500) during inference.  This wrapper retries only backend-termination/
connection failures.  It never retries a graded wrong answer and therefore
cannot turn benchmark FAIL into PASS.
"""
from __future__ import annotations

import sys
import time

from tools import run_top100_round1_stratified as r1
from tools import run_top100_round2_quantization_routing as r2

_ORIGINAL_CHAT = r1.OllamaBenchmarkProvider.chat
_RETRY_MARKERS = (
    "llama-server process has terminated",
    "provider connection failed",
    "HTTP 500",
    "connection reset",
)


def resilient_chat(self: r1.OllamaBenchmarkProvider,
                   messages: list[dict[str, str]]) -> str:
    failures: list[str] = []
    for attempt in range(1, 5):
        try:
            return _ORIGINAL_CHAT(self, messages)
        except RuntimeError as exc:
            text = str(exc)
            if not any(marker.lower() in text.lower() for marker in _RETRY_MARKERS):
                raise
            failures.append(text)
            print(
                f"OLLAMA_TRANSIENT_RETRY model={self.model} attempt={attempt}/4 error={text[:300]}",
                file=sys.stderr,
                flush=True,
            )
            if attempt < 4:
                time.sleep(float(attempt))
    raise RuntimeError(
        "Ollama backend failed after bounded retries: " + " | ".join(failures[-2:])
    )


def main() -> int:
    r1.OllamaBenchmarkProvider.chat = resilient_chat
    return r2.main()


if __name__ == "__main__":
    raise SystemExit(main())
