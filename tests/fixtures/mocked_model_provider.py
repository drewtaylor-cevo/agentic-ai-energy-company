"""Canonical Strands mock Model for offline prompt-level regression tests.

Source: https://github.com/strands-agents/sdk-python/blob/main/tests/fixtures/mocked_model_provider.py
Adapted: AssertionError bounds check on index exhaustion (RESEARCH.md §Pitfall 2)
so a prompt regression that drives N+1 tool calls surfaces as a clear
diagnostic rather than an opaque IndexError.

Use this class wherever you want to exercise the REAL Strands decision
loop against a scripted model — Phase 13.1 Gap 1 shipped because Plan
03/05 tests used synthetic AgentResult fixtures that hard-coded the
tool count, so the tests passed regardless of what the system prompt
actually said. Using a Model-layer mock forces the test to exercise
the real `_run_loop`, hook dispatch, and tool registry.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Iterable, Sequence
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models import Model
from strands.types.content import Message, Messages
from strands.types.event_loop import StopReason
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

T = TypeVar("T", bound=BaseModel)


class MockedModelProvider(Model):
    """Scripted Message → StreamEvent dict sequence implementation of the
    Strands Model interface.

    Usage:
        mock = MockedModelProvider([
            {"role": "assistant", "content": [{"toolUse": {...}}]},  # Turn 1
            {"role": "assistant", "content": [{"toolUse": {...}}]},  # Turn 2
            {"role": "assistant", "content": [{"toolUse": {         # Terminal:
                "name": "RecommendationResponse", ...}}]},           # structured-output
        ])
        agent = Agent(model=mock, system_prompt=SYSTEM_PROMPT, tools=[...],
                       hooks=[_four_tool_cap])
        result = agent("prompt", structured_output_model=RecommendationResponse)

    Bounds-check behaviour (Phase 13.1 D-13.1-15 / RESEARCH.md Pitfall 2):
        If the real prompt drives MORE tool calls than are scripted, the
        next stream() call raises AssertionError with a diagnostic
        message. This surfaces prompt short-circuit regressions as
        test failures rather than opaque IndexErrors.
    """

    def __init__(self, agent_responses: Sequence[Message]):
        self.agent_responses = [*agent_responses]
        self.index = 0

    def get_config(self) -> Any:
        return {}

    def update_config(self, **model_config: Any) -> None:
        pass

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        # Intentionally empty — force-tool path uses stream().
        if False:
            yield  # pragma: no cover

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        tool_choice: Any | None = None,
        *,
        system_prompt_content: Any = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if self.index >= len(self.agent_responses):
            raise AssertionError(
                f"MockedModelProvider: prompt drove "
                f"{self.index + 1} model calls but only "
                f"{len(self.agent_responses)} scripted responses available. "
                f"Likely cause: prompt short-circuit not firing "
                f"(Phase 13.1 Gap 1 regression)."
            )
        events = self._to_events(self.agent_responses[self.index])
        for event in events:
            yield event
        self.index += 1

    def _to_events(self, msg: Message) -> Iterable[dict[str, Any]]:
        stop: StopReason = "end_turn"
        yield {"messageStart": {"role": "assistant"}}
        for block in msg["content"]:
            if "text" in block:
                yield {"contentBlockStart": {"start": {}}}
                yield {"contentBlockDelta": {"delta": {"text": block["text"]}}}
                yield {"contentBlockStop": {}}
            if "toolUse" in block:
                stop = "tool_use"
                yield {
                    "contentBlockStart": {
                        "start": {
                            "toolUse": {
                                "name": block["toolUse"]["name"],
                                "toolUseId": block["toolUse"]["toolUseId"],
                            }
                        }
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "delta": {
                            "toolUse": {
                                "input": json.dumps(block["toolUse"]["input"])
                            }
                        }
                    }
                }
                yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": stop}}
