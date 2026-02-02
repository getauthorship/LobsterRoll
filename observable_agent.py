"""
Agent Governance: Observable Private Language Protocol
Python SDK for creating agents with mandatory English reporting.

This module provides:
- ObservableAgent: Wrapper that enforces novel-language governance
- ProtocolDescriptor: Metadata for registered protocols
- EnglishReport: Structured translation reports
- GatewayClient: HTTP client for the Policy Gateway
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import requests
from requests.exceptions import RequestException

# -----------------------------
# Configuration (override via environment or config file)
# -----------------------------
REPORT_INTERVAL_SEC = 60
REPORT_EVERY_N_MESSAGES = 25
MIN_COVERAGE = 0.95
MIN_SUMMARY_LENGTH = 30

# -----------------------------
# Novelty Detection Heuristics
# Replace with model-based classifier for production use.
# -----------------------------
_english_word_re = re.compile(r"[A-Za-z]{2,}")
_non_ascii_re = re.compile(r"[^\x00-\x7F]+")


def looks_like_english(text: str) -> bool:
    """
    Conservative heuristic: returns True if text is plausibly English.
    
    Flags as non-English/novel:
    - High non-ASCII character ratio
    - Very low vowel ratio
    - Very few recognizable words
    
    For production, replace with:
    - Language model classifier
    - Entropy-based detection
    - Compression ratio analysis
    """
    if not text.strip():
        return True

    # Non-ASCII characters suggest non-English or encoded content
    non_ascii = len(_non_ascii_re.findall(text))
    if non_ascii > 0:
        return False

    # Check for recognizable English words
    words = _english_word_re.findall(text)
    if len(words) < 3 and len(text) > 40:
        return False

    # Vowel ratio check (English typically has ~30-40% vowels)
    vowels = sum(text.lower().count(v) for v in "aeiou")
    letters = sum(c.isalpha() for c in text)
    if letters > 0 and (vowels / letters) < 0.20 and len(text) > 30:
        return False

    return True


def sha256_hex(s: str) -> str:
    """Generate SHA-256 hash as hex string."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# -----------------------------
# Data Structures
# -----------------------------

@dataclass
class ProtocolDescriptor:
    """
    Metadata describing a novel-language protocol.
    Must be registered before using the protocol.
    """
    name: str                  # Unique identifier (e.g., "compressed_coord")
    version: str               # Version string (e.g., "1.0")
    purpose: str               # Why this protocol exists
    scope: str                 # What content it covers
    risk_tier: str             # "low", "medium", "high", "critical"
    translation_method: str    # How English reports are derived
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EnglishReport:
    """
    Mandatory English translation report for novel-language usage.
    Submitted periodically to maintain compliance.
    """
    agent_id: str
    protocol_name: str
    protocol_version: str
    window_start_ts: float          # Unix timestamp
    window_end_ts: float            # Unix timestamp
    message_ids: List[str]          # Hashes of novel-language messages covered
    english_summary: str            # Plain English translation/summary
    coverage: float                 # Fraction of messages covered (0-1)
    self_confidence: float          # Self-rated accuracy (0-1)
    notes: str = ""                 # Optional additional context
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -----------------------------
# Gateway Client
# -----------------------------

class GatewayClient:
    """
    HTTP client for communicating with the Policy Gateway.
    
    In production, this sends real HTTP requests.
    For testing, you can mock the methods.
    """

    def __init__(
        self, 
        base_url: str, 
        api_key: str,
        timeout: float = 30.0,
        verify_ssl: bool = True
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        })

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request to the gateway."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            # Log the error in production
            print(f"[GatewayClient] Error calling {url}: {e}")
            raise

    def register_protocol(self, agent_id: str, pd: ProtocolDescriptor) -> Dict[str, Any]:
        """Register a protocol for an agent."""
        payload = {
            "agent_id": agent_id,
            "protocol": pd.to_dict()
        }
        return self._post("/register_protocol_for_agent", payload)

    def submit_report(self, report: EnglishReport) -> Dict[str, Any]:
        """Submit an English translation report."""
        return self._post("/report", report.to_dict())

    def send_message(
        self, 
        agent_id: str, 
        to: str, 
        content: str, 
        protocol: Optional[Tuple[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send a message through the gateway.
        
        Args:
            agent_id: Sender's agent ID
            to: Recipient's agent ID
            content: Message content
            protocol: Optional (name, version) tuple for novel-language messages
        """
        payload = {
            "from": agent_id,
            "to": to,
            "content": content,
            "protocol": {"name": protocol[0], "version": protocol[1]} if protocol else None,
            "ts": time.time(),
        }
        return self._post("/send", payload)


class MockGatewayClient(GatewayClient):
    """
    Mock gateway client for testing and development.
    Prints actions instead of making HTTP requests.
    """
    
    def __init__(self, base_url: str = "http://localhost:8080", api_key: str = "mock"):
        self.base_url = base_url
        self.api_key = api_key
        self.registered_protocols: Dict[str, Dict[str, ProtocolDescriptor]] = {}
        self.last_report_ts: Dict[str, float] = {}
        self.messages_sent: List[Dict[str, Any]] = []
        self.reports_submitted: List[EnglishReport] = []

    def register_protocol(self, agent_id: str, pd: ProtocolDescriptor) -> Dict[str, Any]:
        """Mock: Store protocol registration."""
        if agent_id not in self.registered_protocols:
            self.registered_protocols[agent_id] = {}
        key = f"{pd.name}:{pd.version}"
        self.registered_protocols[agent_id][key] = pd
        print(f"[MockGateway] Registered protocol {key} for {agent_id}")
        return {"ok": True}

    def submit_report(self, report: EnglishReport) -> Dict[str, Any]:
        """Mock: Store and validate report."""
        key = f"{report.protocol_name}:{report.protocol_version}"
        
        # Validate protocol registration
        if report.agent_id not in self.registered_protocols:
            return {"ok": False, "error": "Agent not registered"}
        if key not in self.registered_protocols[report.agent_id]:
            return {"ok": False, "error": "Protocol not registered"}
        
        # Validate coverage
        if report.coverage < MIN_COVERAGE:
            return {"ok": False, "error": f"Coverage {report.coverage} < {MIN_COVERAGE}"}
        
        # Validate summary length
        if len(report.english_summary.strip()) < MIN_SUMMARY_LENGTH:
            return {"ok": False, "error": "Summary too short"}
        
        self.reports_submitted.append(report)
        self.last_report_ts[f"{report.agent_id}::{key}"] = time.time()
        print(f"[MockGateway] Report accepted from {report.agent_id}")
        print(f"             Summary: {report.english_summary[:100]}...")
        return {"ok": True}

    def send_message(
        self, 
        agent_id: str, 
        to: str, 
        content: str, 
        protocol: Optional[Tuple[str, str]] = None
    ) -> Dict[str, Any]:
        """Mock: Validate and store message."""
        is_english = looks_like_english(content)
        
        if is_english:
            msg = {"from": agent_id, "to": to, "content": content, "kind": "english"}
            self.messages_sent.append(msg)
            print(f"[MockGateway] Message sent (English): {agent_id} → {to}")
            return {"ok": True}
        
        # Novel language checks
        if protocol is None:
            print(f"[MockGateway] REJECTED: Novel language without protocol")
            return {"ok": False, "error": "Novel language requires protocol"}
        
        key = f"{protocol[0]}:{protocol[1]}"
        
        # Check registration
        if agent_id not in self.registered_protocols:
            print(f"[MockGateway] REJECTED: Agent not registered")
            return {"ok": False, "error": "Protocol not registered"}
        if key not in self.registered_protocols[agent_id]:
            print(f"[MockGateway] REJECTED: Protocol {key} not registered")
            return {"ok": False, "error": "Protocol not registered"}
        
        # Check report freshness
        report_key = f"{agent_id}::{key}"
        last = self.last_report_ts.get(report_key, 0)
        if time.time() - last > REPORT_INTERVAL_SEC:
            print(f"[MockGateway] REJECTED: Report overdue")
            return {"ok": False, "error": "Report overdue"}
        
        msg = {"from": agent_id, "to": to, "content": content, "kind": "novel", "protocol": key}
        self.messages_sent.append(msg)
        print(f"[MockGateway] Message sent (Novel): {agent_id} → {to} [{key}]")
        return {"ok": True}


# -----------------------------
# Observable Agent Wrapper
# -----------------------------

class ObservableAgent:
    """
    Wrapper that enforces novel-language governance rules.
    
    Usage:
        agent = ObservableAgent(agent_id="agent-001", gateway=gateway)
        agent.register_protocol(descriptor)
        agent.send("agent-002", "Hello!")  # English - passes through
        agent.send("agent-002", "X9|cmd=1") # Novel - requires report
    """

    def __init__(self, agent_id: str, gateway: GatewayClient) -> None:
        self.agent_id = agent_id
        self.gateway = gateway
        
        self.protocol: Optional[ProtocolDescriptor] = None
        self._novel_buffer: List[Tuple[float, str, str]] = []  # (ts, msg_id, raw_text)
        self._window_start_ts: float = time.time()
        self._last_report_ts: float = 0.0
        self._novel_count_since_report: int = 0

    def register_protocol(self, pd: ProtocolDescriptor) -> None:
        """
        Register a protocol before using novel language.
        Must be called before sending any novel-language messages.
        """
        self.protocol = pd
        self.gateway.register_protocol(self.agent_id, pd)
        # Reset reporting window
        self._last_report_ts = time.time()
        self._window_start_ts = time.time()

    def _needs_report(self) -> bool:
        """Check if a report is required before sending more novel messages."""
        if self._novel_count_since_report == 0:
            return False
        if (time.time() - self._last_report_ts) >= REPORT_INTERVAL_SEC:
            return True
        if self._novel_count_since_report >= REPORT_EVERY_N_MESSAGES:
            return True
        return False

    def _build_english_report(self) -> EnglishReport:
        """
        Build an English translation report for buffered novel messages.
        
        Override this method in subclasses to provide actual translations
        based on your protocol's semantics.
        """
        if self.protocol is None:
            raise RuntimeError("Protocol must be registered before building reports")

        window_end = time.time()
        message_ids = [mid for (_, mid, _) in self._novel_buffer]

        # Default implementation: placeholder summary
        # In production, decode messages using your protocol's translation method
        english_summary = (
            f"English report for protocol {self.protocol.name} v{self.protocol.version}. "
            f"Covered {len(self._novel_buffer)} novel-language messages in this window. "
            f"Translation method: {self.protocol.translation_method}. "
            "Summary: messages contained compressed task state updates and coordination signals; "
            "no external actions should be taken without explicit tool authorization."
        )

        return EnglishReport(
            agent_id=self.agent_id,
            protocol_name=self.protocol.name,
            protocol_version=self.protocol.version,
            window_start_ts=self._window_start_ts,
            window_end_ts=window_end,
            message_ids=message_ids,
            english_summary=english_summary,
            coverage=1.0,  # We include all buffered messages
            self_confidence=0.8,
            notes="Auto-generated report; subject to audit sampling.",
        )

    def _submit_report_and_reset(self) -> None:
        """Submit the current report and reset the reporting window."""
        report = self._build_english_report()

        if report.coverage < MIN_COVERAGE:
            raise RuntimeError(
                f"Report coverage {report.coverage} below minimum {MIN_COVERAGE}"
            )

        result = self.gateway.submit_report(report)
        if not result.get("ok"):
            raise RuntimeError(f"Report rejected: {result.get('error', 'unknown')}")

        # Reset tracking
        self._last_report_ts = time.time()
        self._window_start_ts = self._last_report_ts
        self._novel_buffer.clear()
        self._novel_count_since_report = 0

    def send(self, to: str, content: str) -> Dict[str, Any]:
        """
        Send a message to another agent.
        
        - English messages pass through freely.
        - Novel-language messages require protocol registration and periodic reports.
        
        Args:
            to: Recipient agent ID
            content: Message content
            
        Returns:
            Gateway response dict
            
        Raises:
            PermissionError: If novel language used without protocol registration
            RuntimeError: If report submission fails
        """
        is_english = looks_like_english(content)
        
        if is_english:
            return self.gateway.send_message(
                self.agent_id, to, content, protocol=None
            )

        # Novel language: require protocol registration
        if self.protocol is None:
            raise PermissionError(
                "Novel-language use denied: protocol not registered. "
                "Call register_protocol() first."
            )

        # Buffer this message for reporting
        msg_id = sha256_hex(content + str(time.time()))
        self._novel_buffer.append((time.time(), msg_id, content))
        self._novel_count_since_report += 1

        # Submit report if needed BEFORE sending
        if self._needs_report():
            self._submit_report_and_reset()

        # Send through gateway with declared protocol
        return self.gateway.send_message(
            self.agent_id, 
            to, 
            content, 
            protocol=(self.protocol.name, self.protocol.version)
        )

    def flush_report(self) -> None:
        """
        Force submission of a report for any buffered messages.
        Call this when shutting down or pausing the agent.
        """
        if self._novel_buffer:
            self._submit_report_and_reset()


# -----------------------------
# Example Usage
# -----------------------------

if __name__ == "__main__":
    # Use mock gateway for demonstration
    gateway = MockGatewayClient()
    agent = ObservableAgent(agent_id="agent-123", gateway=gateway)

    # Step 1: Register protocol before any novel language
    agent.register_protocol(
        ProtocolDescriptor(
            name="compressed_coord",
            version="1.0",
            purpose="Efficient multi-agent coordination",
            scope="Internal state deltas + task routing tokens",
            risk_tier="medium",
            translation_method="decode-via-dictionary + LLM paraphrase",
        )
    )

    print("\n--- Sending English message ---")
    agent.send("agent-xyz", "Hi! I will send you an update in a compact form next.")

    print("\n--- Sending novel-language message ---")
    agent.send("agent-xyz", "X9|d=17;u=0x3f;rt=2;ack#77")
    
    print("\n--- Sending more novel messages ---")
    for i in range(5):
        agent.send("agent-xyz", f"CMD|seq={i};state=0x{i:02x}")

    print("\n--- Flushing final report ---")
    agent.flush_report()
    
    print("\n--- Summary ---")
    print(f"Messages sent: {len(gateway.messages_sent)}")
    print(f"Reports submitted: {len(gateway.reports_submitted)}")
