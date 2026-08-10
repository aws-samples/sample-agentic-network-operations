# Neptune MCP Runtime Deployment

This directory contains the deployment configuration for the AWS Labs Amazon Neptune MCP Server as an AgentCore Runtime target behind AgentCore Gateway.

## Overview

The Neptune MCP Runtime exposes Neptune Analytics graph tools through MCP. It deploys the official `awslabs.amazon-neptune-mcp-server` package from PyPI without modifications, maintaining the ability to update from the upstream AWS Labs repository.

The Network Operations Agent connects only to AgentCore Gateway. Gateway invokes this runtime as an MCP server target using its execution role and SigV4 authentication; the agent does not hold a Neptune runtime endpoint, OAuth client, or secret.

## Architecture

```
┌─────────────────────────────────┐
│  Network Operations Agent        │
└──────────────┬──────────────────┘
               │ OAuth
               ▼
┌─────────────────────────────────┐
│  AgentCore Gateway              │
└──────────────┬──────────────────┘
               │ SigV4
               ▼
┌─────────────────────────────────┐
│  Neptune MCP Server             │
│  (AgentCore Runtime)            │
│  ┌───────────────────────────┐  │
│  │ AWS Labs MCP Server       │  │
│  │ (awslabs.amazon-neptune-  │  │
│  │  mcp-server)              │  │
│  └───────────┬───────────────┘  │
└──────────────┼──────────────────┘
               │ AWS SDK
               ▼
        ┌──────────────┐
        │   Neptune    │
        │  Analytics   │
        │   Graph      │
        └──────────────┘
```

## Prerequisites

Before deploying the Neptune MCP Runtime, ensure you have:

1. **AWS Credentials**: Configured with permissions for:
   - AgentCore Runtime deployment
   - ECR repository access
   - Neptune Analytics access
   - CloudWatch Logs access
   - IAM role creation (if auto-creating)

2. **Docker**: Installed and running on your local machine

3. **Python 3.13**: Virtual environment with the project dependencies installed

4. **Neptune Analytics Graph**: Deployed and accessible in the target region
   - Test environment: us-east-1
   - Production environment: us-west-2

5. **Python Dependencies**: Install required packages:
   ```bash
   source .venv/bin/activate
   pip install boto3==1.43.54 bedrock-agentcore-starter-toolkit==0.3.0
   ```

## Configuration

### Environment-Specific Configuration

The deployment supports two environments:

**Test Environment (us-east-1)**:
- Region: `us-east-1`
- Runtime Name: `neptune-mcp-runtime-test`
- Log Level: `INFO`
- Neptune Graph ID: Set with `NEPTUNE_GRAPH_ID`

**Production Environment (us-west-2)**:
- Region: `us-west-2`
- Runtime Name: `neptune-mcp-runtime-prod`
- Log Level: `ERROR`
- Neptune Graph ID: Set with `NEPTUNE_GRAPH_ID`

### Set Deployment Configuration

Before deploying, set the Neptune Analytics graph identifier in the environment:

```bash
export NEPTUNE_GRAPH_ID="g-your-neptune-analytics-graph-id"
```

## Deployment

### Deploy to Test Environment

```bash
# Activate Python 3.13 virtual environment
source .venv/bin/activate

# Configure the target graph without committing its identifier
export NEPTUNE_GRAPH_ID="g-your-test-graph-id"

# Deploy to test environment
python agentcore/neptune_mcp_runtime/deploy_neptune_mcp_runtime.py --env test

# Deploy with verbose logging
python agentcore/neptune_mcp_runtime/deploy_neptune_mcp_runtime.py --env test --verbose
```

### Deploy to Production Environment

```bash
# Activate Python 3.13 virtual environment
source .venv/bin/activate

# Deploy to production environment
python agentcore/neptune_mcp_runtime/deploy_neptune_mcp_runtime.py --env prod
```

### Deployment Output

After successful deployment, the script will output:

```
Deployment Summary:
  Environment: test
  Region: ${AWS_REGION}
  Runtime ARN: ${AGENT_RUNTIME_ARN}
  Runtime ID: ${AGENT_RUNTIME_ID}
  Runtime Endpoint: ${AGENT_RUNTIME_ENDPOINT}
  
Gateway Configuration:
  Target type: MCP server
  Authentication: Gateway IAM role with SigV4
  Target endpoint: URL-encoded AgentCore Runtime invocation URL
  
Logging:
  CloudWatch Logs: Enabled
  Log Group: ${AGENT_RUNTIME_LOG_GROUP}
```

Set the runtime ARN and Lambda ARNs in the Gateway deployment environment before
registering the target. For a test deployment, set the runtime ARN returned by
this script, set the Lambda target ARNs, then deploy the Gateway:

```bash
export NETOPS_TEST_NEPTUNE_MCP_RUNTIME_ARN="<runtime-arn>"
export NETOPS_TEST_PSR_LOOKUP_LAMBDA_ARN="<psr-lookup-lambda-arn>"
export NETOPS_TEST_WORKFORCE_ROUTER_LAMBDA_ARN="<workforce-router-lambda-arn>"
export NETOPS_TEST_POSTCODE_TO_GEO_LAMBDA_ARN="<postcode-lambda-arn>"
export NETOPS_TEST_WEATHER_FORECAST_LAMBDA_ARN="<weather-lambda-arn>"

python agentcore/deploy_agentcore_gateway.py --env test
```

Use the corresponding `NETOPS_PROD_*` variables for production. The Gateway
deployment creates or updates the Neptune MCP Runtime target and waits for it
to become ready before the Network Operations Agent is deployed.

## Gateway Authentication

AgentCore Gateway invokes the runtime with its execution role. Its target configuration uses an IAM credential provider with `bedrock-agentcore` as the SigV4 service and forwards `Mcp-Session-Id` in both directions.

The Gateway execution role requires `bedrock-agentcore:InvokeAgentRuntime` limited to this runtime ARN. The runtime does not require a separate Cognito client for this path.

The Network Operations Agent obtains an OAuth token only for Gateway and discovers the Neptune tools from Gateway's unified catalog.

## Local Development

For local development, install the pinned runtime dependencies and run the
AgentCore-compatible entrypoint.

### Run Locally

```bash
# Install the pinned runtime dependency.
python -m pip install -r agentcore/neptune_mcp_runtime/requirements.txt

# Set your Neptune Analytics graph ID.
export NEPTUNE_GRAPH_ID="g-your-graph-id"

# Optional: defaults to us-east-1.
export AWS_REGION="us-east-1"

# Run the streamable HTTP server.
./agentcore/neptune_mcp_runtime/run_local.sh
```

The runtime uses streamable HTTP, matching the AgentCore Runtime deployment.
For an end-to-end check, deploy the runtime, update its Gateway target, and
invoke the topology tools through AgentCore Gateway.

### Test the Local MCP Transport

With the same dependencies, graph ID, AWS credentials, and region configured,
run:

```bash
python agentcore/neptune_mcp_runtime/test_local_mcp.py
```

The test starts a temporary local runtime on an available loopback port, checks
the documented MCP tool catalog, and invokes an openCypher query and schema
request over streamable HTTP. It does not conflict with a separately running
`run_local.sh` server.

## MCP Tools

The Network Operations Agent discovers the upstream MCP tool catalog through
AgentCore Gateway at runtime. With the pinned Neptune MCP server version, the
agent uses the following Neptune Analytics tools:

### 1. `run_opencypher_query`

Execute an openCypher query against the Neptune Analytics graph.

### 2. `get_graph_schema`

Retrieve the graph schema so the agent can identify valid node labels, edge
types, and properties before querying.

### 3. `get_graph_status`

Check whether the Neptune Analytics graph is available.

Verify the catalog through Gateway after updating the pinned upstream package.
This sample does not expose Gremlin queries.

## Updating to New Versions

To update to a new version of the AWS Labs Neptune MCP server:

1. **Update `requirements.txt`**:
   ```text
   awslabs.amazon-neptune-mcp-server==1.2.3
   ```

2. **Test Locally**:
   ```bash
   source .venv/bin/activate
   python -m pip install -r agentcore/neptune_mcp_runtime/requirements.txt
   export NEPTUNE_GRAPH_ID="g-your-graph-id"
   ./agentcore/neptune_mcp_runtime/run_local.sh
   ```

3. **Redeploy**:
   ```bash
   python agentcore/neptune_mcp_runtime/deploy_neptune_mcp_runtime.py --env test
   ```

4. **Validate**:
   - Confirm Gateway discovers the expected tools
   - Test an openCypher query and schema retrieval through Gateway
   - Verify CloudWatch logs

## Troubleshooting

### Runtime Fails to Start

**Symptom**: Runtime stuck in "CREATING" status

**Solutions**:
- Check CloudWatch logs for errors
- Verify IAM role has Neptune Analytics permissions
- Verify Docker image is valid
- Check NEPTUNE_ENDPOINT environment variable format

### Gateway Authentication Fails

**Symptom**: The Network Operations Agent receives a 401 response from
AgentCore Gateway.

**Solutions**:
- Verify the Gateway JWT authorizer and allowed client configuration.
- Verify the agent has the configured Gateway ID and HTTPS endpoint.
- Check the agent runtime logs for OAuth token-acquisition errors.

### Gateway Cannot Invoke the Runtime

**Symptom**: Gateway reports `AccessDenied` or cannot synchronize the Neptune
MCP Runtime target.

**Solutions**:
- Verify the target references the intended runtime ARN and region.
- Verify the Gateway execution role has `bedrock-agentcore:InvokeAgentRuntime`
  limited to that runtime ARN.
- Verify the runtime target status is `READY` before deploying the agent.

### Query Fails

**Symptom**: Query execution errors

**Solutions**:
- Verify Neptune Analytics graph is in "Available" status
- Check openCypher query syntax
- Verify IAM role has `neptune-graph:ExecuteQuery` permission
- Check CloudWatch logs for detailed error messages

### Permission Denied

**Symptom**: IAM permission errors

**Solutions**:
- Verify IAM role has required permissions:
  - `neptune-graph:ExecuteQuery`
  - `neptune-graph:GetGraph`
  - `neptune-graph:GetGraphSummary`
- Check IAM role trust policy allows bedrock-agentcore.amazonaws.com
- Verify graph ARN in IAM policy matches deployed graph

### Query Timeout

**Symptom**: Query exceeds maximum execution time

**Solutions**:
- Simplify query
- Add LIMIT clause to reduce result set
- Optimize graph structure
- Check Neptune Analytics query timeout settings

## Cleanup

Delete test resources when they are no longer needed to avoid ongoing charges:

1. Remove the Neptune MCP Runtime target from AgentCore Gateway, then delete
   the test runtime using the AgentCore console or control-plane API.
2. Delete the test Gateway if it is not used by other samples.
3. Delete or stop the test Neptune Analytics graph after exporting any data
   that must be retained.
4. Review the CloudFormation stack's retained S3 data and access-log buckets;
   remove their contents and buckets only when retention requirements permit.

The sample intentionally retains S3 data buckets to avoid accidental data loss
during stack deletion.

## Monitoring

### CloudWatch Logs

View runtime logs in CloudWatch:

```bash
# View logs
aws logs tail /aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/runtime-abc123 --follow

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/runtime-abc123 \
  --filter-pattern "ERROR"
```

### Metrics

Monitor runtime health:
- Query execution time
- Query success/failure rate
- Authentication success/failure rate
- Runtime availability

## Cost Considerations

### Neptune Analytics Pricing
- **Graph Storage**: ~$0.10/GB/month
- **Query Compute**: ~$0.10 per million graph traversals

### AgentCore Runtime Pricing
- **Runtime Hosting**: Based on compute time and memory
- **Data Transfer**: Standard AWS data transfer rates

### Cost Optimization
- Use appropriate log levels (ERROR in prod, INFO in test)
- Optimize queries to reduce traversals
- Monitor usage with CloudWatch metrics
- Delete unused runtimes

## Support

For issues or questions:
- Check CloudWatch logs for detailed error messages
- Review AWS Labs Neptune MCP server documentation
- Check Neptune Analytics documentation
- Review AgentCore Runtime documentation

## Files

- `Dockerfile`: Docker image definition for Neptune MCP server
- `main.py`: Streamable HTTP runtime entrypoint
- `run_local.sh`: Local runtime launcher
- `test_local_mcp.py`: MCP development test utility
- `deploy_neptune_mcp_runtime.py`: Deployment script
- `README.md`: This file
