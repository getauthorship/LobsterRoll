"""
Agent Governance: Observable Private Language Protocol

A framework for allowing AI agents to use optimized/private communication
protocols only if they continuously produce human-readable English reports.
"""

from .observable_agent import (
    ObservableAgent,
    ProtocolDescriptor,
    EnglishReport,
    GatewayClient,
    MockGatewayClient,
    looks_like_english,
    REPORT_INTERVAL_SEC,
    REPORT_EVERY_N_MESSAGES,
    MIN_COVERAGE,
)

__version__ = "1.0.0"
__all__ = [
    "ObservableAgent",
    "ProtocolDescriptor", 
    "EnglishReport",
    "GatewayClient",
    "MockGatewayClient",
    "looks_like_english",
    "REPORT_INTERVAL_SEC",
    "REPORT_EVERY_N_MESSAGES",
    "MIN_COVERAGE",
]
