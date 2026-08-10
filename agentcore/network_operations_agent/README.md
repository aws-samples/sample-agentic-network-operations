# Network Operations Agent

A Strands-based AI agent that provides intelligent operational decision support for electricity distribution network operations.

## Overview

The Network Operations Agent connects to one OAuth-protected service to answer complex operational questions:

1. **AgentCore Gateway**: Provides the Neptune Analytics graph-query tools together with PSR (Priority Services Register), workforce, postcode, and weather tools.

Gateway connects to the Neptune MCP Runtime using IAM authentication. The agent has no direct Neptune endpoint or runtime credential.

By combining the Gateway tools, the agent can:
- Identify affected properties during substation failures
- Rank substations by PSR customer impact
- Recommend optimal backfeed strategies
- Analyze multi-substation failure scenarios

## Local testing

agentcore dev

agentcore invoke --dev '{"prompt":"The Southport and Wigan primary substations have failed. Which primary substation should I backfeed from to get the most people on the PSR register back on supply?"}'

## Project Structure

```
agentcore/network_operations_agent/
├── src/
│   ├── __init__.py           # Package initialization
│   └── main.py               # Runtime entrypoint and configuration
├── config.test.json          # Test environment config
├── config.prod.json          # Production environment config
└── README.md                 # This file
```

## Configuration

The agent uses JSON configuration files for environment-specific settings:

- `config.test.json`: Test environment (us-east-1, INFO logging)
- `config.prod.json`: Production environment (us-west-2, INFO logging)

### Configuration Format

```json
{
  "environment": "test",
  "aws_region": "us-east-1",
  "agentcore_gateway": {
    "gateway_id": "${AGENTCORE_GATEWAY_ID}",
    "endpoint": "${AGENTCORE_GATEWAY_ENDPOINT}"
  },
  "logging": {
    "level": "INFO",
    "format": "json"
  }
}
```

### Configuration Fields

#### AgentCore Gateway
- `gateway_id`: Gateway identifier for dynamic Cognito discovery (from gateway deployment)
- `endpoint`: Gateway MCP endpoint URL - the `resourceUrl` from the gateway (must be HTTPS)
  - Format: `https://{gateway-id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp`

Set these values at deployment time rather than committing a Gateway identifier
or endpoint:

```bash
export AGENTCORE_GATEWAY_ID="your-gateway-id"
export AGENTCORE_GATEWAY_ENDPOINT="https://your-gateway-id.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
```

#### Logging
- `level`: Log level (DEBUG, INFO, WARNING, ERROR)
- `format`: Log format (json or text)

## Usage

### Loading Configuration

```python
from src.config import AgentConfig

# Load configuration from file
config = AgentConfig.load_from_file("config.test.json")

# Access configuration values
print(f"Environment: {config.environment}")
print(f"AWS Region: {config.aws_region}")
print(f"Gateway ID: {config.agentcore_gateway.gateway_id}")
```

### Configuration Validation

The configuration loader performs comprehensive validation:

1. **File existence**: Checks if config file exists
2. **JSON validity**: Validates JSON syntax
3. **Required fields**: Ensures all required fields are present
4. **Field validation**: Validates individual field values (e.g., HTTPS URLs)
5. **Fail-fast**: Raises clear error messages if validation fails

## Requirements

- Python 3.13+
- boto3 (for AWS SDK)
- strands (for agent framework)

## Next Steps

1. Deploy or update the Gateway after deploying the Neptune MCP Runtime.
2. Set the Gateway environment variables and deploy the Network Operations Agent.
3. Confirm the Gateway discovers the expected Neptune and Lambda tools.

## Demonstration Data

This agent is a demonstration project. Its example network, customer, PSR, workforce, and operational data are synthetic and must not be treated as production data.

## License

Project-authored code and synthetic data are licensed under [MIT-0](../../LICENSE).
