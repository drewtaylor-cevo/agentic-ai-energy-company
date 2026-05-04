"""Phase 15 WF-01: AgentCore Memory configuration helpers.

Builds deterministic Memory session keys scoped to customer + UTC date.

CRITICAL DISTINCTION (AP-2 prevention):
  - `runtimeSessionId` = fresh uuid4 per invocation (SC-3, Pitfall 2).
    This is the AgentCore RUNTIME session — identifies a single request/response
    cycle. Generated INSIDE handler() / invoke(), never at module scope.
  - Memory `session_id` = deterministic f"{customer_id}-{UTC-ISO-day}".
    This is the AgentCore MEMORY session — groups all interactions for the
    same customer on the same calendar day. Used for turn-1 → turn-2 recall.
  - Memory `actor_id` = f"customer:{customer_id}".
    This is the ISOLATION boundary — prevents cross-customer PII bleed (C4).

These are orthogonal AWS concepts. Do NOT conflate them.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
    from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

logger = logging.getLogger(__name__)


def build_memory_config(
    memory_id: str,
    customer_id: str,
    session_date: str,
) -> "AgentCoreMemoryConfig":
    """Build Memory config with deterministic session_id and customer-scoped actorId.

    Args:
        memory_id: AgentCore Memory resource ID (from MEMORY_ID env var).
        customer_id: Customer identifier (e.g. "CUST-001").
        session_date: UTC ISO date string (e.g. "2026-05-03").

    Returns:
        AgentCoreMemoryConfig ready for AgentCoreMemorySessionManager.
    """
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig

    config = AgentCoreMemoryConfig(
        memory_id=memory_id,
        # Deterministic: same customer + same day = same session.
        session_id=f"{customer_id}-{session_date}",
        # Structural isolation: each customer is a separate actor (C4 prevention).
        actor_id=f"customer:{customer_id}",
    )
    logger.debug(
        "Memory config: memory_id=%s actor_id=customer:%s session_id=%s-%s",
        memory_id, customer_id, customer_id, session_date,
    )
    return config


def build_session_manager(
    config: "AgentCoreMemoryConfig",
    region: str,
) -> "AgentCoreMemorySessionManager":
    """Build Strands-compatible session manager from Memory config.

    Args:
        config: AgentCoreMemoryConfig from build_memory_config().
        region: AWS region (e.g. "us-east-1").

    Returns:
        AgentCoreMemorySessionManager wired to the Memory resource.
    """
    from bedrock_agentcore.memory.integrations.strands.session_manager import (
        AgentCoreMemorySessionManager,
    )

    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=region,
    )
