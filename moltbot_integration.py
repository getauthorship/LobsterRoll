"""
Example: Integrating Agent Governance with MoltBot/MoltBook

This file shows how to wrap your existing MoltBot agents with
the governance framework to enable novel-language use with
mandatory English reporting.
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Import from the agent_governance package
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python.observable_agent import (
    ObservableAgent,
    ProtocolDescriptor,
    EnglishReport,
    GatewayClient,
    MockGatewayClient,
)


# =============================================================================
# Example 1: Basic MoltBot Integration
# =============================================================================

class GovernedMoltBotAgent(ObservableAgent):
    """
    Example of wrapping a MoltBot agent with governance.
    
    Replace the placeholder methods with your actual MoltBot logic.
    """
    
    def __init__(
        self, 
        agent_id: str,
        moltbot_config: Dict[str, Any],
        gateway_url: str = "http://localhost:8080",
        api_key: str = "dev-key"
    ):
        # Initialize the gateway client
        gateway = GatewayClient(base_url=gateway_url, api_key=api_key)
        super().__init__(agent_id=agent_id, gateway=gateway)
        
        # Store MoltBot-specific config
        self.moltbot_config = moltbot_config
        
        # Your protocol's encoding/decoding logic
        self._encoding_table: Dict[str, str] = {}
        self._decoding_table: Dict[str, str] = {}
    
    def setup_protocol(self, protocol_name: str = "moltbot_coord"):
        """Register the governance protocol on startup."""
        self.register_protocol(
            ProtocolDescriptor(
                name=protocol_name,
                version="1.0",
                purpose="MoltBot multi-agent coordination",
                scope="Task assignments, state sync, acknowledgments",
                risk_tier="medium",
                translation_method="lookup_table_with_context"
            )
        )
    
    def encode_message(self, message: Dict[str, Any]) -> str:
        """
        Encode a structured message to your compressed format.
        Replace with your actual encoding logic.
        """
        # Example: Simple key-value encoding
        parts = []
        for key, value in message.items():
            parts.append(f"{key}={value}")
        return "|".join(parts)
    
    def decode_message(self, encoded: str) -> Dict[str, Any]:
        """
        Decode a compressed message back to structured form.
        Replace with your actual decoding logic.
        """
        result = {}
        for part in encoded.split("|"):
            if "=" in part:
                key, value = part.split("=", 1)
                result[key] = value
        return result
    
    def _build_english_report(self) -> EnglishReport:
        """
        Override to provide actual translations based on your protocol.
        """
        if self.protocol is None:
            raise RuntimeError("Protocol not registered")
        
        # Decode all buffered messages
        decoded_messages = []
        for ts, msg_id, raw in self._novel_buffer:
            try:
                decoded = self.decode_message(raw)
                decoded_messages.append(decoded)
            except Exception as e:
                decoded_messages.append({"_raw": raw, "_error": str(e)})
        
        # Generate human-readable summary
        summary_parts = []
        for i, msg in enumerate(decoded_messages):
            if "task" in msg:
                summary_parts.append(f"Task assignment: {msg.get('task')}")
            elif "ack" in msg:
                summary_parts.append(f"Acknowledged message {msg.get('ack')}")
            elif "state" in msg:
                summary_parts.append(f"State update: {msg.get('state')}")
            else:
                summary_parts.append(f"Message {i+1}: {msg}")
        
        english_summary = (
            f"MoltBot coordination report ({len(self._novel_buffer)} messages). "
            + "; ".join(summary_parts[:10])  # Limit to first 10 for brevity
        )
        if len(summary_parts) > 10:
            english_summary += f" ... and {len(summary_parts) - 10} more."
        
        return EnglishReport(
            agent_id=self.agent_id,
            protocol_name=self.protocol.name,
            protocol_version=self.protocol.version,
            window_start_ts=self._window_start_ts,
            window_end_ts=__import__('time').time(),
            message_ids=[mid for _, mid, _ in self._novel_buffer],
            english_summary=english_summary,
            coverage=1.0,
            self_confidence=0.9,
            notes="Decoded using MoltBot lookup tables"
        )
    
    def send_task_assignment(self, to: str, task_id: str, priority: int):
        """High-level method to assign a task to another agent."""
        encoded = self.encode_message({
            "cmd": "assign",
            "task": task_id,
            "pri": priority
        })
        return self.send(to, encoded)
    
    def send_acknowledgment(self, to: str, message_id: str):
        """High-level method to acknowledge a message."""
        encoded = self.encode_message({
            "cmd": "ack",
            "ref": message_id
        })
        return self.send(to, encoded)


# =============================================================================
# Example 2: Tiered Risk Protocol
# =============================================================================

class TieredGovernanceAgent(ObservableAgent):
    """
    Example showing different reporting intervals based on risk tier.
    """
    
    RISK_INTERVALS = {
        "low": 120,      # 2 minutes
        "medium": 60,    # 1 minute
        "high": 15,      # 15 seconds
        "critical": 5,   # 5 seconds
    }
    
    def __init__(self, agent_id: str, gateway: GatewayClient, risk_tier: str = "medium"):
        super().__init__(agent_id, gateway)
        self.risk_tier = risk_tier
    
    def _needs_report(self) -> bool:
        """Override to use risk-based intervals."""
        if self._novel_count_since_report == 0:
            return False
        
        interval = self.RISK_INTERVALS.get(self.risk_tier, 60)
        
        import time
        if (time.time() - self._last_report_ts) >= interval:
            return True
        
        # Also check message count (scales with risk)
        max_messages = {
            "low": 50,
            "medium": 25,
            "high": 10,
            "critical": 5,
        }.get(self.risk_tier, 25)
        
        return self._novel_count_since_report >= max_messages


# =============================================================================
# Example 3: Protocol with External Evaluator
# =============================================================================

@dataclass
class EvaluatorResult:
    """Result from an external fidelity evaluator."""
    fidelity_score: float  # 0-1
    issues: List[str]
    approved: bool


class EvaluatedAgent(ObservableAgent):
    """
    Agent that sends reports through an external evaluator
    for fidelity verification before submission.
    """
    
    def __init__(
        self, 
        agent_id: str, 
        gateway: GatewayClient,
        evaluator_url: Optional[str] = None
    ):
        super().__init__(agent_id, gateway)
        self.evaluator_url = evaluator_url
    
    def _evaluate_report(self, report: EnglishReport) -> EvaluatorResult:
        """
        Send report to external evaluator for verification.
        Replace with actual HTTP call to your evaluator service.
        """
        if self.evaluator_url is None:
            # No evaluator configured - auto-approve
            return EvaluatorResult(
                fidelity_score=report.self_confidence,
                issues=[],
                approved=True
            )
        
        # In production: POST to evaluator service
        # response = requests.post(
        #     self.evaluator_url,
        #     json={
        #         "report": report.to_dict(),
        #         "raw_messages": [msg for _, _, msg in self._novel_buffer]
        #     }
        # )
        # return EvaluatorResult(**response.json())
        
        # Placeholder
        return EvaluatorResult(
            fidelity_score=0.85,
            issues=[],
            approved=True
        )
    
    def _submit_report_and_reset(self) -> None:
        """Override to include evaluation step."""
        report = self._build_english_report()
        
        # Evaluate before submitting
        eval_result = self._evaluate_report(report)
        
        if not eval_result.approved:
            raise RuntimeError(
                f"Report failed evaluation: {eval_result.issues}"
            )
        
        # Adjust confidence based on evaluator
        report.self_confidence = min(
            report.self_confidence, 
            eval_result.fidelity_score
        )
        
        # Now submit to gateway
        result = self.gateway.submit_report(report)
        if not result.get("ok"):
            raise RuntimeError(f"Report rejected: {result.get('error')}")
        
        # Reset
        import time
        self._last_report_ts = time.time()
        self._window_start_ts = self._last_report_ts
        self._novel_buffer.clear()
        self._novel_count_since_report = 0


# =============================================================================
# Demo
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Agent Governance - MoltBot Integration Demo")
    print("=" * 60)
    
    # Use mock gateway for demo
    mock_gateway = MockGatewayClient()
    
    # Create a governed MoltBot agent
    agent = GovernedMoltBotAgent(
        agent_id="moltbot-001",
        moltbot_config={"model": "gpt-4", "temperature": 0.7},
        gateway_url="http://localhost:8080",
        api_key="demo-key"
    )
    
    # Swap in mock gateway for demo
    agent.gateway = mock_gateway
    
    # Setup the protocol
    agent.setup_protocol()
    
    print("\n--- Sending task assignments ---")
    agent.send_task_assignment("moltbot-002", "task_001", priority=1)
    agent.send_task_assignment("moltbot-002", "task_002", priority=2)
    agent.send_task_assignment("moltbot-003", "task_003", priority=1)
    
    print("\n--- Sending acknowledgments ---")
    agent.send_acknowledgment("moltbot-002", "msg_123")
    
    print("\n--- Flushing final report ---")
    agent.flush_report()
    
    print("\n--- Demo complete ---")
    print(f"Total messages: {len(mock_gateway.messages_sent)}")
    print(f"Total reports: {len(mock_gateway.reports_submitted)}")
    
    if mock_gateway.reports_submitted:
        print("\nLast report summary:")
        print(f"  {mock_gateway.reports_submitted[-1].english_summary[:200]}...")
