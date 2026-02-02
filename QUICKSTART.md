# Quickstart Guide

Get up and running with Agent Governance in 5 minutes.

---

## Prerequisites

- Python 3.8+ (for SDK)
- Rust 1.70+ (for Gateway)
- Docker (optional, for containerized deployment)

---

## Option 1: Quick Demo (Mock Gateway)

Test the Python SDK without running the real gateway:

```bash
cd python
pip install -r requirements.txt
python observable_agent.py
```

This runs a demo with a mock gateway that prints events to console.

---

## Option 2: Full Stack

### Step 1: Start the Gateway

```bash
cd rust
cargo run --release
```

You should see:
```
{"timestamp":"...","level":"INFO","message":"Policy Gateway listening","address":"0.0.0.0:8080"}
```

### Step 2: Verify Gateway Health

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{"ok":true,"message":"Gateway operational"}
```

### Step 3: Run a Python Agent

In a new terminal:

```bash
cd python
pip install -r requirements.txt

# Edit the demo to use real gateway
python -c "
from observable_agent import ObservableAgent, ProtocolDescriptor, GatewayClient

# Connect to real gateway
gw = GatewayClient('http://localhost:8080', 'test-key')
agent = ObservableAgent('demo-agent', gw)

# Register protocol
agent.register_protocol(ProtocolDescriptor(
    name='demo',
    version='1.0',
    purpose='Testing',
    scope='Demo messages',
    risk_tier='low',
    translation_method='manual'
))

# Send messages
agent.send('other-agent', 'Hello in English!')
agent.send('other-agent', 'X9|cmd=test')  # Novel language
agent.flush_report()

print('Success!')
"
```

---

## Option 3: Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f policy-gateway

# Stop services
docker-compose down
```

---

## What's Next?

1. **Read the full README** - Understand the architecture and policy rules
2. **Check the Policy Spec** - See `docs/POLICY.md` for detailed requirements
3. **Explore Examples** - See `examples/moltbot_integration.py` for MoltBot usage
4. **Customize Your Protocol** - Define your own encoding and translation methods

---

## Common Issues

### "Connection refused" when contacting gateway

Make sure the gateway is running:
```bash
curl http://localhost:8080/health
```

### "Protocol not registered" error

Always call `register_protocol()` before sending novel-language messages:
```python
agent.register_protocol(descriptor)  # Do this first!
agent.send(to, message)              # Then send
```

### "Report overdue" error

The SDK handles this automatically, but if you're calling the gateway directly, submit a report before sending more novel messages.

---

## Getting Help

- Check existing issues in the repository
- Review the policy specification in `docs/POLICY.md`
- Look at the example code in `examples/`
