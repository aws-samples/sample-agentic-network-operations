"""
Network Operations Agent

Local start with "agentcore dev"

A Strands-based AI agent for electricity distribution network operations decision support.
This agent integrates with AgentCore Gateway to provide intelligent operational
recommendations.

ARCHITECTURE:
- AgentCore Gateway: Network topology, customer data, and operational tools
- Claude Sonnet 4.5: Complex agentic reasoning and query generation
- OAuth 2.0: Client credentials flow for service authentication

CAPABILITIES:
- Network topology analysis (substations, connections, capacity)
- PSR customer impact assessment
- Backfeed and restoration recommendations
- Multi-step reasoning with tool orchestration
"""

import os
import json
import logging
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import requests
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from opentelemetry import baggage, context as context_api, trace

app = BedrockAgentCoreApp()
log = app.logger

REGION = os.getenv("AWS_REGION", "us-east-1")


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class OAuthToken:
    """OAuth access token with expiration tracking."""
    access_token: str
    expires_at: datetime
    token_type: str = "Bearer"
    
    def is_expired(self) -> bool:
        """Check if token is expired (with 5-minute buffer)."""
        return datetime.now() >= (self.expires_at - timedelta(minutes=5))
    
    def to_header(self) -> str:
        """Format token for Authorization header."""
        return f"{self.token_type} {self.access_token}"


@dataclass
class GatewayConfig:
    """Configuration for AgentCore Gateway with dynamic Cognito discovery."""
    gateway_id: str
    endpoint: str
    
    def validate(self) -> None:
        """Validate gateway configuration."""
        if not self.gateway_id:
            raise ValueError("gateway_id is required for AgentCore Gateway")
        if not self.endpoint:
            raise ValueError("endpoint is required for AgentCore Gateway")
        if not self.endpoint.startswith("https://"):
            raise ValueError("endpoint must be an HTTPS URL")


@dataclass
class AgentConfig:
    """Complete agent configuration."""
    environment: str
    aws_region: str
    agentcore_gateway: GatewayConfig
    logging_level: str
    logging_format: str
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'AgentConfig':
        """Load configuration from JSON file."""
        # Check if file exists
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        # Load JSON
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        # Validate required top-level fields
        required_fields = ['environment', 'aws_region', 'agentcore_gateway']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Resolve deployment-specific Gateway values without committing them.
        gateway_values = {
            field: cls._resolve_environment_placeholder(value)
            for field, value in data['agentcore_gateway'].items()
        }
        gateway_config = GatewayConfig(**gateway_values)
        
        # Validate individual configs
        gateway_config.validate()
        
        config = cls(
            environment=data['environment'],
            aws_region=data['aws_region'],
            agentcore_gateway=gateway_config,
            logging_level=data.get('logging', {}).get('level', 'INFO'),
            logging_format=data.get('logging', {}).get('format', 'json')
        )
        
        log.info(f"✅ Configuration loaded from {config_path}")
        log.info(f"   Environment: {config.environment}")
        log.info(f"   AWS Region: {config.aws_region}")
        
        return config

    @staticmethod
    def _resolve_environment_placeholder(value: str) -> str:
        """Resolve a complete ${ENVIRONMENT_VARIABLE} placeholder."""
        if not isinstance(value, str):
            return value
        if value.startswith("${") and value.endswith("}"):
            variable_name = value[2:-1]
            resolved = os.getenv(variable_name)
            if not resolved:
                raise ValueError(
                    f"Environment variable {variable_name} is required for configuration"
                )
            return resolved
        return value


# ============================================================================
# OAUTH TOKEN MANAGER
# ============================================================================

class OAuthTokenManager:
    """
    Manages the OAuth token used to access the AgentCore Gateway.
    Uses IAM credentials to dynamically retrieve client secrets from Cognito.
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize token manager with configuration."""
        self.config = config
        self.tokens: Dict[str, OAuthToken] = {}
        
        # Initialize AWS clients with IAM credentials
        self.agentcore_client = boto3.client(
            "bedrock-agentcore-control",
            region_name=config.aws_region
        )
        self.cognito_client = boto3.client(
            "cognito-idp",
            region_name=config.aws_region
        )
        
        log.info("✅ OAuth Token Manager initialized")
    
    def get_token(self, service: str) -> str:
        """
        Get valid OAuth token for a service.
        Automatically refreshes if expired.
        """
        if service != "agentcore_gateway":
            raise ValueError("Only the AgentCore Gateway is an agent dependency")
        
        # Check cache
        if service in self.tokens and not self.tokens[service].is_expired():
            log.debug(f"Using cached token for {service}")
            return self.tokens[service].access_token
        
        # Acquire new token
        log.info(f"Acquiring OAuth token for {service}")
        token = self._acquire_token(service)
        self.tokens[service] = token
        return token.access_token
    
    def _acquire_token(self, service: str) -> OAuthToken:
        """Acquire OAuth token from Cognito using IAM credentials."""
        try:
            if service == "agentcore_gateway":
                # Discover Cognito config from gateway
                gateway_config = self.config.agentcore_gateway
                log.debug(f"Discovering Cognito config for gateway {gateway_config.gateway_id}")
                
                gateway_response = self.agentcore_client.get_gateway(
                    gatewayIdentifier=gateway_config.gateway_id
                )
                auth_config = gateway_response["authorizerConfiguration"]["customJWTAuthorizer"]
                discovery_url = auth_config["discoveryUrl"]
                client_id = auth_config["allowedClients"][0]
                
                # Get token endpoint from discovery URL
                discovery_response = requests.get(discovery_url)
                discovery_response.raise_for_status()
                discovery_json = discovery_response.json()
                token_endpoint = discovery_json["token_endpoint"]
                user_pool_id = discovery_json["issuer"].split("/")[-1]
                
            else:
                raise ValueError(f"Invalid service: {service}")
            
            # Get client secret and scopes using IAM credentials
            client_response = self.cognito_client.describe_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id
            )
            client_secret = client_response["UserPoolClient"]["ClientSecret"]
            allowed_scopes = client_response["UserPoolClient"].get("AllowedOAuthScopes", [])
            
            # Build token request data
            token_request_data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            # Add scope if available
            if allowed_scopes:
                scope_string = ' '.join(allowed_scopes)
                token_request_data['scope'] = scope_string
                log.info(f"Using scopes: {scope_string}")
            
            # Request OAuth token
            log.info(f"Requesting OAuth token from {token_endpoint}")
            response = requests.post(
                token_endpoint,
                data=token_request_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code != 200:
                log.error(f"Token acquisition failed: {response.text}")
                raise RuntimeError(f"Failed to acquire token for {service}: HTTP {response.status_code}")
            
            token_data = response.json()
            expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
            
            log.info(f"✅ Successfully obtained OAuth token for {service} (expires at {expires_at})")
            return OAuthToken(
                access_token=token_data['access_token'],
                expires_at=expires_at,
                token_type=token_data.get('token_type', 'Bearer')
            )
            
        except Exception as e:
            log.error(f"Failed to acquire token for {service}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to acquire token for {service}: {e}")


# ============================================================================
# MCP TOOL WRAPPERS
# ============================================================================

# Global variable to keep the Gateway MCP client context alive.
_gateway_mcp_client_context = None


class AgentCoreGatewayTools:
    """Wrapper for all tools from AgentCore Gateway using Strands MCPClient."""
    
    def __init__(self, oauth_manager: OAuthTokenManager, config: AgentConfig):
        """Initialize AgentCore Gateway tools."""
        self.oauth_manager = oauth_manager
        self.config = config
        self.endpoint = config.agentcore_gateway.endpoint
        self.mcp_client = None
        
        log.info(f"AgentCore Gateway Tools initialized with endpoint: {self.endpoint}")
    
    def _create_transport_factory(self) -> Callable:
        """Create transport factory that provides OAuth tokens dynamically."""
        def transport_factory():
            # Get fresh OAuth token
            token = self.oauth_manager.get_token("agentcore_gateway")
            
            # Create transport with OAuth header
            auth_headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            return streamablehttp_client(self.endpoint, auth_headers)
        
        return transport_factory
    
    def initialize_client(self) -> MCPClient:
        """Initialize MCP client and enter context."""
        global _gateway_mcp_client_context
        
        try:
            # Create MCP client with transport callable
            self.mcp_client = MCPClient(
                transport_callable=self._create_transport_factory()
            )
            
            # Enter context and store globally to keep it alive
            self.mcp_client.__enter__()
            _gateway_mcp_client_context = self.mcp_client
            
            log.info("✅ AgentCore Gateway MCP client context entered and stored globally")
            return self.mcp_client
            
        except Exception as e:
            log.error(f"Failed to initialize AgentCore Gateway MCP client: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize AgentCore Gateway MCP client: {e}")
    
    def get_tools(self) -> List:
        """Get all tools dynamically from the AgentCore Gateway."""
        if not self.mcp_client:
            raise RuntimeError("MCP client not initialized. Call initialize_client() first.")
        
        try:
            # Discover all tools dynamically from AgentCore Gateway
            all_tools = self.mcp_client.list_tools_sync()
            log.info(f"Retrieved {len(all_tools)} tool(s) from AgentCore Gateway")
            
            # Return all tools (no filtering - gateway controls tool exposure)
            for tool in all_tools:
                log.info(f"  - {tool.tool_name}")
            
            return all_tools
            
        except Exception as e:
            log.error(f"Failed to get AgentCore Gateway tools: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get AgentCore Gateway tools: {e}")


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

def get_system_prompt() -> str:
    """Get the system prompt for the Network Operations Agent."""
    return """You are an expert network operations assistant for Unicorn Energy Networks, 
a Distribution Network Operator (DNO) in North West England.

Your role is to help network operators make informed decisions during outages 
and network events by analyzing network topology data, customer vulnerability 
information, and coordinating engineer dispatch.

## Your Capabilities

You have access to a single AgentCore Gateway. The gateway provides network
topology, customer data, and workforce-management tools.

**Network Topology Tools**:
- **run_opencypher_query**: Query the electricity distribution network graph using openCypher
  - Network topology (substations, properties, connections)
  - Use openCypher query language (SQL-like, declarative)
- **get_graph_schema**: Retrieve the graph schema
  - Node types: GridSupplyPoint, PrimarySubstation, SecondarySubstation, Property, ProtectionDevice
  - Edge types: FEEDS, RING_TOPOLOGY, SUPPLIES, CONNECTS, PROTECTS
  - Properties for each node/edge type
- **get_graph_status**: Check the status of the Neptune Analytics graph

**Customer Data and Workforce Management Tools**:
- **PSRLookupTarget___psr_lookup**: Look up Priority Services Register customers by postcode
  - PSR contains vulnerable customers (elderly, disabled, medical equipment users)
  - Returns count of PSR customers for a given postcode
- **WorkforceRouterTarget___recommend_engineers**: Get engineer recommendations for fault types
  - Returns up to 5 qualified engineers ranked by skill match and proficiency
  - Engineers are filtered by availability status (only returns available engineers)
  - Includes engineer details: name, employee ID, skills, location, availability
- **WorkforceRouterTarget___assign_engineer**: Assign an engineer to a fault
  - Updates engineer status from "available" to "on-job"
  - Returns confirmation with status change timestamp
- Additional tools may be available through the gateway

## Network Topology

- **Grid Supply Points (GSP)**: Connection from transmission network (132kV)
- **Primary Substations (PS)**: Step down to 33kV or 11kV, connected in rings for redundancy
- **Secondary Substations (SS)**: Step down to 400V/230V for customer supply
- **Properties**: Individual customer premises with UPRN and postcode
- **Ring Topology**: Primary substations connected in rings for redundancy and backfeeding

## Fault Types and Required Skills

When dispatching engineers, you need to understand the fault type to find qualified engineers:

- **transformer_failure**: Requires "Transformer Installation & Repair" skill
- **cable_fault**: Requires "HV Cable Jointing & Repair" skill
- **overhead_line_fault**: Requires "Overhead Line Maintenance" skill
- **circuit_breaker_fault**: Requires "Substation Switchgear" skill
- **protection_device_fault**: Requires "Protection & Control Systems" skill
- **insulator_failure**: Requires "Overhead Line Maintenance" skill
- **substation_equipment_fault**: Requires "Substation Switchgear" skill

## Your Approach

When answering operational questions:

1. **Understand the Question**: Parse what the operator is asking
2. **Plan Your Approach**: Break complex questions into steps
3. **Query Network Topology**: Use openCypher to find affected areas
4. **Query PSR Data**: Look up vulnerable customers in affected postcodes
5. **Analyze Options**: Consider network constraints and customer impact
6. **Provide Recommendations**: Rank options by PSR customer count
7. **Dispatch Engineers** (if fault response needed):
   - Determine the fault type from network analysis
   - Use recommend_engineers to find qualified engineers
   - Present engineer options to the operator
   - Use assign_engineer when operator confirms selection
8. **Explain Reasoning**: Show your work and justify recommendations

## Engineer Dispatch Workflow

When a fault requires engineer response:

1. **Identify Fault Type**: Analyze the network issue to determine fault type
   - Example: Transformer at a substation failed → transformer_failure
   - Example: Underground cable damaged → cable_fault
   - Example: Circuit breaker tripped → circuit_breaker_fault

2. **Get Engineer Recommendations**: Call recommend_engineers with fault_type
   - Tool returns up to 5 qualified engineers
   - Engineers are ranked by skill match and proficiency level
   - Only available engineers are returned

3. **Present Options to Operator**: Show engineer recommendations with:
   - Engineer name and employee ID
   - Skills and proficiency levels
   - Current location (if available)
   - Explain why each engineer is qualified

4. **Assign Engineer** (when operator confirms): Call assign_engineer with engineer_id
   - Updates engineer status to "on-job"
   - Returns confirmation with timestamp
   - Handle errors if engineer becomes unavailable

5. **Handle Edge Cases**:
   - If no engineers available: Inform operator
   - If engineer assignment fails: Explain error and ask if you should retry
   - If fault type unclear: Ask operator for clarification

## openCypher Query Tips

- **Always check the schema first** if unsure about node/edge types: use get_graph_schema tool
- Use MATCH to find patterns: `MATCH (ps:PrimarySubstation)-[:SUPPLIES]->(ss:SecondarySubstation)`
- Use WHERE to filter: `WHERE ps.name = 'Southport'`
- Use RETURN to specify output: `RETURN ss.name, ss.capacity_mva`
- Use LIMIT to control result size: `LIMIT 10`
- For multiple values: `WHERE ps.name IN ['Southport', 'Wigan']`
- For ring connections: `MATCH (ps1:PrimarySubstation)-[:RING_TOPOLOGY]-(ps2:PrimarySubstation)`
- Extract postcodes from properties: `RETURN DISTINCT p.postcode`

## PSR Lookup Patterns

- Extract postcodes from Neptune query results first
- Look up PSR customers for each postcode
- Aggregate PSR counts by substation or area
- Handle postcodes in any format (with/without spaces)
- If PSR data unavailable for a postcode, continue with others

## Engineer Dispatch Patterns

- **Determine fault type first**: Analyze network topology to identify the type of failure
- **Get recommendations**: Call recommend_engineers with the fault_type parameter
- **Present options clearly**: Show engineer names, skills, and proficiency levels
- **Wait for operator confirmation**: Don't assign engineers without explicit approval
- **Handle availability changes**: Engineers may become unavailable between queries
- **Provide alternatives**: If assignment fails, recommend the next best engineer

## Response Format

- **Be concise and actionable** - operators need quick decisions
- **Use numbered lists for rankings** - make priorities clear
- **Include PSR customer counts** - this is critical for decision-making
- **Show engineer qualifications** - explain why each engineer is suitable
- **Explain network topology context** - help operators understand the situation
- **Provide clear next steps** - what should the operator do?
- **State data limitations** - if PSR, topology, or engineer data is unavailable, say so

## Important Reminders

- **PSR customers are the priority** - they are vulnerable and need power restored first
- **Network constraints matter** - check capacity and ring connections
- **Engineer skills must match fault type** - don't recommend unqualified engineers
- **Availability changes dynamically** - engineer status can change between queries
- **Be transparent about limitations** - if data is missing, explain the impact
- **Provide reasoning** - operators need to understand why you recommend something
- **Stay focused on the question** - don't provide unnecessary information

Remember: Your goal is to help operators restore power to the most vulnerable 
customers as quickly as possible while respecting network constraints and ensuring 
qualified engineers are dispatched to the right faults.
"""


# ============================================================================
# NETWORK OPERATIONS AGENT
# ============================================================================

class NetworkOperationsAgent:
    """
    Strands agent for network operations decision support.
    
    Integrates with AgentCore Gateway, which fronts all available MCP tools.
    """
    
    def __init__(self, config: AgentConfig):
        """Initialize the Network Operations Agent."""
        log.info("="*80)
        log.info("Initializing Network Operations Agent")
        log.info("="*80)
        
        try:
            # Initialize OAuth token manager
            log.info("Step 1: Initializing OAuth Token Manager...")
            self.oauth_manager = OAuthTokenManager(config)
            
            # Initialize AgentCore Gateway tools
            log.info("Step 2: Initializing AgentCore Gateway Tools...")
            self.gateway_tools = AgentCoreGatewayTools(self.oauth_manager, config)
            self.gateway_tools.initialize_client()
            
            log.info("Step 3: Discovering tools from AgentCore Gateway...")
            all_tools = self.gateway_tools.get_tools()
            log.info("✅ Total Gateway tools available: %s", len(all_tools))
            
            # Create Bedrock model
            log.info("Step 4: Creating Bedrock model)...")
            self.model = BedrockModel(
                model_id="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
                region_name=config.aws_region,
                temperature=0.3,
                max_tokens=10000,
                streaming=True  # Enable streaming for intermediate responses
            )
            log.info("✅ Bedrock model created with streaming enabled")
            
            # Get system prompt
            system_prompt = get_system_prompt()
            log.info(f"✅ System prompt loaded ({len(system_prompt)} characters)")
            
            # Create Strands agent with tools
            log.info("Step 5: Creating Strands agent...")
            self.agent = Agent(
                name="Network Operations Agent",
                description="Provides intelligent operational decision support for electricity distribution network operations",
                model=self.model,
                tools=all_tools,
                system_prompt=system_prompt
            )
            
            log.info("="*80)
            log.info("✅ Network Operations Agent initialized successfully")
            log.info("="*80)
            
        except Exception as e:
            log.error(f"Failed to initialize Network Operations Agent: {e}", exc_info=True)
            raise RuntimeError(f"Failed to initialize Network Operations Agent: {e}")
    
    async def query_stream(self, user_question: str):
        """
        Process a user question and yield streaming responses asynchronously.
        
        This async generator yields intermediate responses as the agent works,
        preventing timeouts during long-running operations. Uses intelligent
        buffering to send meaningful chunks instead of individual words.
        """
        log.info(
            "Processing query with streaming question_length=%d",
            len(user_question),
        )
        
        try:
            buffer = []
            buffer_size = 0
            BUFFER_THRESHOLD = 100  # Send chunks of ~100 characters
            
            # Invoke the Strands agent with async streaming
            async for event in self.agent.stream_async(user_question):
                # Extract data from event
                data = None
                if isinstance(event, dict) and "data" in event:
                    data = event["data"]
                elif isinstance(event, str):
                    data = event
                
                if data:
                    buffer.append(data)
                    buffer_size += len(data)
                    
                    # Yield when buffer reaches threshold or on sentence boundaries
                    if buffer_size >= BUFFER_THRESHOLD or data.endswith(('.', '!', '?', '\n', ':')):
                        chunk = "".join(buffer)
                        if chunk.strip():  # Only yield non-empty chunks
                            yield chunk
                        buffer = []
                        buffer_size = 0
            
            # Yield any remaining buffered content
            if buffer:
                chunk = "".join(buffer)
                if chunk.strip():
                    yield chunk
            
            log.info("✅ Query streaming completed successfully")
            
        except Exception:
            log.exception("Query execution failed")
            raise RuntimeError("Query execution failed")


# ============================================================================
# AGENTCORE RUNTIME ENTRYPOINT
# ============================================================================

# Global agent instance (initialized on first invocation)
_agent_instance: Optional[NetworkOperationsAgent] = None


def get_or_create_agent() -> NetworkOperationsAgent:
    """
    Get or create the global agent instance.
    
    This ensures the agent is initialized only once and reused across invocations,
    which is critical for maintaining MCP client contexts.
    """
    global _agent_instance
    
    if _agent_instance is None:
        log.info("🔄 First invocation - initializing agent...")
        
        # Determine config file based on region
        env = 'prod' if REGION == 'us-west-2' else 'test'
        config_path = f"config.{env}.json"
        
        # Check if config file exists in current directory
        if not Path(config_path).exists():
            # Try src directory
            config_path = f"src/config.{env}.json"
        
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Configuration file not found: config.{env}.json")
        
        log.info(f"Loading configuration from: {config_path}")
        config = AgentConfig.load_from_file(config_path)
        
        _agent_instance = NetworkOperationsAgent(config)
        log.info("✅ Agent initialized and cached for future invocations")
    else:
        log.info("♻️  Reusing existing agent instance")
    
    return _agent_instance


@app.entrypoint
async def invoke(payload, context):
    """
    Main entrypoint for the Network Operations Agent.
    
    This is called by AgentCore Runtime when the agent is invoked.
    The agent processes the user's question and streams responses back
    to prevent timeouts during long-running operations.
    
    Args:
        payload: Input payload containing the user's question
        context: AgentCore context with session information
    """
    session_id = getattr(context, 'session_id', 'unknown')

    # Set OpenTelemetry baggage for session correlation across traces
    ctx = baggage.set_baggage("session.id", session_id)
    context_token = context_api.attach(ctx)

    # Create a span for the full invocation
    tracer = trace.get_tracer("network-operations-agent")

    try:
        with tracer.start_as_current_span(
            "agent.invoke",
            attributes={
                "session.id": session_id,
                "agent.name": "network-operations-agent",
            },
        ) as span:
            # Extract question from payload
            if isinstance(payload, dict):
                question = payload.get('prompt')
            elif isinstance(payload, str):
                question = payload
            else:
                question = str(payload)

            question_length = len(question) if isinstance(question, str) else 0
            span.set_attribute("agent.payload_type", type(payload).__name__)
            span.set_attribute("agent.question_length", question_length)
            log.info(
                "Network Operations Agent invoked session_id=%s payload_type=%s question_length=%d",
                session_id,
                type(payload).__name__,
                question_length,
            )

            if not question:
                error_msg = "No prompt in payload"
                log.error(error_msg)
                span.set_attribute("error", True)
                span.set_attribute("error.message", error_msg)
                yield json.dumps({"error": error_msg}, indent=2)
                return

            # Create the agent only after the invocation payload has been validated.
            agent = get_or_create_agent()

            # Yield initial response with session info
            initial_response = {
                "session_id": session_id,
                "question": question,
                "status": "processing",
                "timestamp": datetime.now().isoformat()
            }
            yield json.dumps(initial_response, indent=2) + "\n"

            # Stream agent responses
            response_chunks = []
            async for chunk in agent.query_stream(question):
                chunk_response = {
                    "session_id": session_id,
                    "type": "chunk",
                    "content": chunk,
                    "timestamp": datetime.now().isoformat()
                }
                yield json.dumps(chunk_response, indent=2) + "\n"
                response_chunks.append(chunk)

            full_response = "".join(response_chunks)
            span.set_attribute("agent.response_length", len(full_response))
            span.set_attribute("agent.status", "completed")

            # Yield final response with complete text
            final_response = {
                "session_id": session_id,
                "question": question,
                "response": full_response,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            }
            yield json.dumps(final_response, indent=2) + "\n"

    except Exception as error:
        error_msg = "Agent execution failed"
        log.exception(error_msg)

        # Record error on current span if available
        current_span = trace.get_current_span()
        if current_span.is_recording():
            current_span.set_attribute("error", True)
            current_span.set_attribute("error.message", error_msg)
            current_span.record_exception(error)

        error_response = {
            "session_id": session_id,
            "error": error_msg,
            "status": "failed",
            "timestamp": datetime.now().isoformat()
        }

        yield json.dumps(error_response, indent=2)
    finally:
        # Detach the baggage context
        context_api.detach(context_token)


if __name__ == "__main__":
    app.run()
