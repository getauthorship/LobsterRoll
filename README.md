# Agent Governance: Observable Private Language Protocol

**Version:** 1.0.0  
**License:** MIT

A governance framework that allows AI agents to use optimized/private communication protocols **only if** they continuously produce human-readable English reports. This enables efficiency gains from agent-to-agent compression while maintaining full human oversight.

---

## Overview

When AI agents communicate, they may develop or use compressed encodings that are more efficient than natural language. This framework makes such "novel language" permissible under strict observability requirements:

| Agents Want | Humans Need | This Framework Provides |
|-------------|-------------|------------------------|
| Efficient encoding | Interpretability | Mandatory English reports |
| Fast coordination | Audit trail | Append-only event logging |
| Private protocols | Kill switch | Gateway enforcement |

**Core Principle:** Novel language is treated as "optimized encoding"—allowed only when humans can continuously verify what's being communicated.

---

## Quick Start

### For Python Users (Agent SDK)

```bash
pip install -r python/requirements.txt
python python/observable_agent.py
```

### For Rust Users (Policy Gateway)

```bash
cd rust
cargo build --release
./target/release/policy_gateway
```

### Full Stack (Both Components)

```bash
# Terminal 1: Start the gateway
cd rust && cargo run --release

# Terminal 2: Run an agent
cd python && python observable_agent.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         HUMAN OVERSIGHT                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  Dashboard UI   │  │  Audit Reports  │  │  Alert System       │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│           │                    │                       │             │
└───────────┼────────────────────┼───────────────────────┼─────────────┘
            │                    │                       │
            ▼                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       POLICY GATEWAY (Rust)                          │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │  Classifier  │  │  Compliance  │  │  Audit Log (append-only)   │ │
│  │ English/Novel│  │   Checker    │  │  - Raw messages (encrypted)│ │
│  └──────────────┘  └──────────────┘  │  - English reports         │ │
│                                       │  - Protocol registrations  │ │
│         ┌─────────────────────────┐  └────────────────────────────┘ │
│         │    ENFORCEMENT RULES    │                                  │
│         │  • Protocol registered? │                                  │
│         │  • Report current?      │                                  │
│         │  • Coverage ≥95%?       │                                  │
│         └─────────────────────────┘                                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  Agent A    │     │  Agent B    │     │  Agent C    │
    │ (Python SDK)│     │ (Python SDK)│     │ (Python SDK)│
    └─────────────┘     └─────────────┘     └─────────────┘
```

---

## Policy Rules

### 1. Registration Rule

Before using any novel language, an agent **must** register a `ProtocolDescriptor`:

```python
agent.register_protocol(
    ProtocolDescriptor(
        name="compressed_coord",           # Unique identifier
        version="1.0",                     # Version string
        purpose="Multi-agent coordination", # Why this protocol exists
        scope="Internal state deltas",     # What it covers
        risk_tier="medium",                # low, medium, high
        translation_method="dictionary",   # How reports are generated
    )
)
```

### 2. Reporting Cadence Rule

If an agent sends novel-language messages, it **must** submit an English report:
- Every **60 seconds**, OR
- Every **25 messages**
- Whichever comes first

### 3. Translation Completeness Rule

Reports must include:

| Field | Requirement |
|-------|-------------|
| `coverage` | ≥ 95% of novel messages since last report |
| `self_confidence` | Self-rated translation accuracy (0-1) |
| `message_ids` | Hashes linking to raw messages |
| `english_summary` | Plain English explanation (≥30 chars) |

### 4. Gating Rule (Enforced by Gateway)

The gateway **rejects**:
- Novel-language messages from unregistered protocols
- Messages from agents with overdue reports
- Messages from agents whose last report failed validation

### 5. Progressive Enforcement

| Violation | Action |
|-----------|--------|
| 1st | Throttle + warning |
| 2nd | Quarantine (read-only mode) |
| 3rd | Disable agent credential |

---

## Python SDK Reference

### Installation

```bash
cd python
pip install -r requirements.txt
```

### Basic Usage

```python
from observable_agent import ObservableAgent, ProtocolDescriptor, GatewayClient

# Connect to the policy gateway
gateway = GatewayClient(
    base_url="http://localhost:8080",
    api_key="your-api-key"
)

# Create an observable agent
agent = ObservableAgent(agent_id="agent-001", gateway=gateway)

# Register your protocol BEFORE using novel language
agent.register_protocol(
    ProtocolDescriptor(
        name="my_protocol",
        version="1.0",
        purpose="Task coordination",
        scope="State synchronization",
        risk_tier="low",
        translation_method="lookup_table"
    )
)

# English messages pass through freely
agent.send("agent-002", "Hello! I'll send a compressed update next.")

# Novel-language messages require protocol registration
agent.send("agent-002", "X9|st=17;f=0x3a;ack#42")  # Triggers report check
```

### Custom Translation

Override `_build_english_report()` for your protocol:

```python
class MyAgent(ObservableAgent):
    def _build_english_report(self) -> EnglishReport:
        # Decode your novel messages to English here
        decoded_messages = [self.decode(msg) for _, _, msg in self._novel_buffer]
        
        summary = "Coordinated task assignments: " + "; ".join(decoded_messages)
        
        return EnglishReport(
            agent_id=self.agent_id,
            protocol_name=self.protocol.name,
            protocol_version=self.protocol.version,
            window_start_ts=self._window_start_ts,
            window_end_ts=time.time(),
            message_ids=[mid for _, mid, _ in self._novel_buffer],
            english_summary=summary,
            coverage=1.0,
            self_confidence=0.95,
        )
```

---

## Rust Gateway Reference

### Building

```bash
cd rust
cargo build --release
```

### Running

```bash
./target/release/policy_gateway
# Listens on http://127.0.0.1:8080
```

### API Endpoints

#### `POST /register_protocol_for_agent`

Register a protocol for an agent.

```json
{
  "agent_id": "agent-001",
  "protocol": {
    "name": "compressed_coord",
    "version": "1.0",
    "purpose": "Multi-agent coordination",
    "scope": "Internal state deltas",
    "risk_tier": "medium",
    "translation_method": "dictionary"
  }
}
```

#### `POST /report`

Submit an English translation report.

```json
{
  "agent_id": "agent-001",
  "protocol_name": "compressed_coord",
  "protocol_version": "1.0",
  "window_start_ts": 1706745600.0,
  "window_end_ts": 1706745660.0,
  "message_ids": ["abc123...", "def456..."],
  "english_summary": "Exchanged task queue updates: Agent assigned task #17, acknowledged completion of task #42.",
  "coverage": 1.0,
  "self_confidence": 0.9,
  "notes": "Auto-generated"
}
```

#### `POST /send`

Send a message (gated by compliance).

```json
{
  "from": "agent-001",
  "to": "agent-002",
  "content": "X9|st=17;f=0x3a;ack#42",
  "protocol": {
    "name": "compressed_coord",
    "version": "1.0"
  },
  "ts": 1706745665.0
}
```

**Response Codes:**

| Code | Meaning |
|------|---------|
| 200 | Message accepted |
| 400 | Report validation failed (coverage, summary length) |
| 403 | Protocol not registered |
| 429 | Report overdue—submit report to continue |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REPORT_INTERVAL_SEC` | 60 | Max seconds between reports |
| `REPORT_EVERY_N_MESSAGES` | 25 | Max messages before report required |
| `MIN_COVERAGE` | 0.95 | Minimum coverage fraction |
| `MIN_SUMMARY_LENGTH` | 30 | Minimum English summary characters |
| `RETENTION_DAYS` | 30 | Audit log retention period |

### Python Config

Edit `python/config.py`:

```python
REPORT_INTERVAL_SEC = 60
REPORT_EVERY_N_MESSAGES = 25
MIN_COVERAGE = 0.95
```

### Rust Config

Edit constants in `rust/src/main.rs`:

```rust
const REPORT_INTERVAL_SEC: u64 = 60;
```

---

## Integration with MoltBot/MoltBook

### Option 1: Sidecar Deployment

Deploy the gateway as a sidecar container:

```yaml
# docker-compose.yml
services:
  policy-gateway:
    build: ./rust
    ports:
      - "8080:8080"
    volumes:
      - ./audit-logs:/var/log/audit
    
  moltbot:
    image: moltbot:latest
    environment:
      - GATEWAY_URL=http://policy-gateway:8080
    depends_on:
      - policy-gateway
```

### Option 2: Library Integration

Import the Python SDK directly:

```python
# In your MoltBot agent code
from agent_governance import ObservableAgent, ProtocolDescriptor

class MyMoltBotAgent(ObservableAgent):
    def __init__(self, moltbot_config):
        gateway = GatewayClient(
            base_url=moltbot_config.gateway_url,
            api_key=moltbot_config.api_key
        )
        super().__init__(
            agent_id=moltbot_config.agent_id,
            gateway=gateway
        )
```

### Option 3: Network Proxy

Configure MoltBot to route all agent traffic through the gateway:

```
[Agent A] → [Policy Gateway :8080] → [Agent B]
                    ↓
              [Audit Log]
```

---

## Extending the Framework

### Custom Novelty Detection

Replace `looks_like_english()` with a model-based classifier:

```python
def looks_like_english(text: str) -> bool:
    # Option 1: Use a language model
    result = classifier.predict(text)
    return result.label == "english" and result.confidence > 0.9
    
    # Option 2: Entropy-based detection
    entropy = calculate_entropy(text)
    return entropy < ENGLISH_ENTROPY_THRESHOLD
    
    # Option 3: Compression ratio
    compressed = zlib.compress(text.encode())
    ratio = len(compressed) / len(text)
    return ratio > ENGLISH_COMPRESSION_RATIO
```

### Report Fidelity Verification

Add an evaluator agent that spot-checks reports:

```python
class ReportEvaluator:
    def verify(self, report: EnglishReport, raw_messages: List[str]) -> float:
        """Returns fidelity score 0-1."""
        # Decode messages using declared method
        decoded = self.decode_messages(raw_messages, report.protocol_name)
        
        # Compare against report summary
        similarity = self.semantic_similarity(decoded, report.english_summary)
        
        return similarity
```

### Tiered Protocol Risk

Adjust reporting frequency by risk tier:

```python
REPORT_INTERVALS = {
    "low": 120,      # 2 minutes
    "medium": 60,    # 1 minute  
    "high": 15,      # 15 seconds
    "critical": 5,   # 5 seconds + mandatory evaluator
}
```

---

## Audit & Compliance

### Log Format

All events are logged with:

```json
{
  "timestamp": "2024-02-01T12:00:00Z",
  "event_type": "msg_accepted|msg_rejected|report_accepted|report_rejected",
  "agent_id": "agent-001",
  "protocol": "compressed_coord:1.0",
  "reason": "...",
  "details": {}
}
```

### Querying Audit Logs

```bash
# Find all rejected messages
grep "msg_rejected" audit.log | jq '.reason'

# Find agents with overdue reports  
grep "report_overdue" audit.log | jq -r '.agent_id' | sort | uniq -c

# Export compliance summary
./scripts/compliance_report.sh --from 2024-01-01 --to 2024-01-31
```

### Compliance Dashboard

The gateway exposes metrics at `/metrics`:

- `agent_compliance_status` (per agent)
- `novel_messages_total` (counter)
- `english_messages_total` (counter)
- `reports_submitted_total` (counter)
- `compliance_violations_total` (counter by severity)

---

## Troubleshooting

### "Protocol not registered"

**Cause:** Trying to send novel-language messages before calling `register_protocol()`.

**Fix:** Always register before sending:

```python
agent.register_protocol(descriptor)  # Do this first!
agent.send(to, novel_message)        # Now this works
```

### "Report overdue"

**Cause:** More than 60 seconds (or 25 messages) since last report.

**Fix:** The SDK handles this automatically. If you're calling the gateway directly, submit a report first:

```bash
curl -X POST http://localhost:8080/report -d '{"agent_id": "...", ...}'
```

### "Coverage below minimum"

**Cause:** Report doesn't cover enough of the novel messages sent.

**Fix:** Ensure your `_build_english_report()` includes all buffered messages.

### Gateway not reachable

**Cause:** Gateway not running or wrong URL.

**Fix:** 
```bash
# Check gateway is running
curl http://localhost:8080/health

# Verify URL in agent config
export GATEWAY_URL=http://localhost:8080
```

---

## Security Considerations

1. **API Authentication:** In production, require API keys for all gateway endpoints
2. **TLS:** Always use HTTPS between agents and gateway
3. **Log Encryption:** Encrypt raw messages at rest; keep reports in plaintext for auditing
4. **Access Control:** Restrict who can read audit logs and modify protocol registrations
5. **Rate Limiting:** Prevent DoS by limiting registration and message rates per agent

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with tests

For major changes, please open an issue first to discuss the proposed changes.
