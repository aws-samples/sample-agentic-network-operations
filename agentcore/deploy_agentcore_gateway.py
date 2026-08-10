#!/usr/bin/env python3
"""

Network Operations Gateway Deployment Script

This script deploys an AgentCore Gateway with Lambda function tools and a
Neptune MCP Runtime target for the North West England Electricity Distribution
Network operations.

PREREQUISITES:
1. Install required packages:
   pip install bedrock-agentcore-starter-toolkit==0.3.0 boto3==1.43.54

2. Configure AWS credentials (one of):
   - AWS CLI: aws configure
   - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
   - IAM role (if running on EC2)

3. Deploy Lambda functions using SAM:
   sam build && sam deploy

4. Set target identifiers for the environment before deployment:
   NETOPS_TEST_PSR_LOOKUP_LAMBDA_ARN
   NETOPS_TEST_WORKFORCE_ROUTER_LAMBDA_ARN
   NETOPS_TEST_POSTCODE_TO_GEO_LAMBDA_ARN
   NETOPS_TEST_WEATHER_FORECAST_LAMBDA_ARN
   NETOPS_TEST_NEPTUNE_MCP_RUNTIME_ARN

USAGE:
    # Deploy to test environment (us-east-1)
    python deploy_agentcore_gateway.py --env test

    # Deploy to production environment (us-west-2)  
    python deploy_agentcore_gateway.py --env prod

    # Deploy with verbose logging
    python deploy_agentcore_gateway.py --env test --verbose

    # Force recreation of gateway (delete and recreate)
    python deploy_agentcore_gateway.py --env test --force-recreate

WHAT THIS SCRIPT DOES:
1. Validates AWS credentials and prerequisites
2. Checks if gateway already exists (idempotent)
3. Creates AgentCore Gateway with OAuth authentication (if needed)
4. Configures Gateway targets:
   - PSR Lookup: Check Priority Services Register status for postcodes
   - Workforce Router: Get engineer recommendations and assign engineers to faults
   - Neptune MCP Runtime: Query the network topology graph
5. Configures CloudWatch logging and metrics

IDEMPOTENCY:
- Script checks for existing gateway and reuses it
- Targets are updated if they already exist
- Safe to run multiple times as you add new tools

ENVIRONMENTS:
- test: Deploys to us-east-1 region
- prod: Deploys to us-west-2 region

The script will output the gateway URL and authentication details upon successful completion.
"""

import argparse
import logging
import os
import sys
import json
import time
from fnmatch import fnmatchcase
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import quote
import boto3
from boto3.session import Session
from botocore.exceptions import NoCredentialsError, ClientError, ProfileNotFound
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient


# Environment-specific AWS regions
TEST_REGION = "us-east-1"
PROD_REGION = "us-west-2"

# Gateway name pattern (keep short - AWS has 60 char limit for derived names)
GATEWAY_NAME_PATTERN = "netops-gateway-{env}"

LAMBDA_TARGET_ENVIRONMENTS = {
    "psr_lookup": "PSR_LOOKUP_LAMBDA_ARN",
    "workforce_router": "WORKFORCE_ROUTER_LAMBDA_ARN",
    "convert_postcode_to_latitude_and_longitude": "POSTCODE_TO_GEO_LAMBDA_ARN",
    "get_forecast_at_latlong": "WEATHER_FORECAST_LAMBDA_ARN",
}

NEPTUNE_RUNTIME_ENVIRONMENT = "NEPTUNE_MCP_RUNTIME_ARN"

NEPTUNE_MCP_TARGET_NAME = "NeptuneMCPRuntimeTarget"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger('psr_gateway_deploy')
    logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


def get_region_for_environment(env: str) -> str:
    """Get the AWS region for the specified environment."""
    return PROD_REGION if env == "prod" else TEST_REGION


def get_gateway_name(env: str) -> str:
    """Get the gateway name for the specified environment."""
    return GATEWAY_NAME_PATTERN.format(env=env)


def get_required_deployment_value(env: str, name: str) -> str:
    """Read a target identifier from the environment-specific deployment config."""
    variable_name = f"NETOPS_{env.upper()}_{name}"
    value = os.getenv(variable_name)
    if not value:
        raise ValueError(
            f"{variable_name} must be set before deploying the AgentCore Gateway"
        )
    return value


def get_lambda_target_arns(env: str) -> Dict[str, str]:
    """Load Lambda target ARNs without committing account-specific identifiers."""
    return {
        tool_name: get_required_deployment_value(env, environment_name)
        for tool_name, environment_name in LAMBDA_TARGET_ENVIRONMENTS.items()
    }


def get_neptune_mcp_runtime_configuration(env: str) -> Dict[str, str]:
    """Load the Neptune runtime target ARN from deployment-time configuration."""
    return {
        "arn": get_required_deployment_value(env, NEPTUNE_RUNTIME_ENVIRONMENT),
        "qualifier": "DEFAULT",
    }


def build_agentcore_runtime_endpoint(runtime_arn: str, region: str, qualifier: str) -> str:
    """Build the URL-encoded AgentCore Runtime invocation endpoint."""
    encoded_arn = quote(runtime_arn, safe="")
    encoded_qualifier = quote(qualifier, safe="")
    return (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
        f"{encoded_arn}/invocations?qualifier={encoded_qualifier}"
    )


def get_neptune_mcp_target_configuration(env: str, region: str) -> Dict[str, Any]:
    """Return the Gateway target configuration for the Neptune MCP Runtime."""
    runtime = get_neptune_mcp_runtime_configuration(env)
    runtime_arn = runtime["arn"]

    return {
        "name": NEPTUNE_MCP_TARGET_NAME,
        "description": "Network topology tools served by the Neptune MCP AgentCore Runtime.",
        "targetConfiguration": {
            "mcp": {
                "mcpServer": {
                    "endpoint": build_agentcore_runtime_endpoint(
                        runtime_arn,
                        region,
                        runtime["qualifier"],
                    ),
                    "listingMode": "DEFAULT",
                }
            }
        },
        "credentialProviderConfigurations": [
            {
                "credentialProviderType": "GATEWAY_IAM_ROLE",
                "credentialProvider": {
                    "iamCredentialProvider": {
                        "service": "bedrock-agentcore",
                        "region": region,
                    }
                },
            }
        ],
        "metadataConfiguration": {
            "allowedRequestHeaders": ["Mcp-Session-Id"],
            "allowedResponseHeaders": ["Mcp-Session-Id"],
        },
    }


def validate_prerequisites(logger: logging.Logger) -> bool:
    """Validate all prerequisites for deployment."""
    logger.info("Validating prerequisites...")
    
    # Validate AWS credentials
    try:
        session = Session()
        sts_client = session.client('sts')
        identity = sts_client.get_caller_identity()
        
        logger.info("AWS credentials validated successfully")
        logger.info(f"Account ID: {identity.get('Account', 'Unknown')}")
        logger.info(f"User/Role ARN: {identity.get('Arn', 'Unknown')}")
        
    except (NoCredentialsError, ProfileNotFound, ClientError) as e:
        logger.error(f"AWS credentials validation failed: {e}")
        return False
    
    return True


def find_existing_gateway(gateway_name: str, region: str, logger: logging.Logger) -> Optional[Dict[str, Any]]:
    """
    Find existing gateway by name using boto3.
    
    Args:
        gateway_name: Name of the gateway to find
        region: AWS region
        logger: Logger instance
    
    Returns:
        Gateway details if found, None otherwise
    """
    try:
        logger.info(f"Checking for existing gateway: {gateway_name}")
        
        # Use boto3 bedrock-agentcore-control client to list gateways
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        
        # List all gateways
        response = client.list_gateways()
        
        # Debug: log all gateways found (response uses 'items' not 'gateways')
        gateways = response.get('items', [])
        logger.info(f"Found {len(gateways)} gateway(s) in account")
        for gw in gateways:
            logger.info(f"  Gateway: name='{gw.get('name')}', id={gw.get('gatewayId')}, status={gw.get('status')}")
        
        # Find gateway with matching name
        for gateway_summary in gateways:
            if gateway_summary.get('name') == gateway_name:
                gateway_id = gateway_summary.get('gatewayId')
                logger.info(f"✅ Found existing gateway: {gateway_id}")
                
                # Get full gateway details
                gateway_details = client.get_gateway(gatewayIdentifier=gateway_id)
                return gateway_details
        
        logger.info(f"No existing gateway found with name: {gateway_name}")
        return None
        
    except Exception as e:
        logger.warning(f"Could not check for existing gateway: {e}")
        logger.debug(f"Exception details: {e}", exc_info=True)
        return None


def delete_gateway(gateway_id: str, region: str, logger: logging.Logger) -> bool:
    """
    Delete an existing gateway using GatewayClient.
    
    Args:
        gateway_id: Gateway ID to delete
        region: AWS region
        logger: Logger instance
    
    Returns:
        True if successful, False otherwise
    """
    try:
        gateway_client = GatewayClient(region_name=region)
        
        logger.info(f"Deleting gateway: {gateway_id}")
        # The toolkit should handle gateway deletion
        # For now, we'll use boto3 directly
        client = boto3.client('bedrock-agent-runtime', region_name=region)
        client.delete_gateway(gatewayIdentifier=gateway_id)
        
        logger.info("✅ Gateway deletion initiated")
        logger.info("⏳ Waiting 30s for deletion to complete...")
        time.sleep(30)
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete gateway: {e}")
        return False


def configure_gateway_logging(gateway: Dict[str, Any], region: str, logger: logging.Logger) -> bool:
    """
    Configure CloudWatch logging for the gateway to enable observability.
    
    AgentCore Gateway does not automatically configure log destinations.
    This function manually configures CloudWatch Logs delivery for gateway observability data
    including metrics, request/response logs, and error messages.
    """
    logger.info("Configuring CloudWatch logging for gateway observability...")
    
    try:
        gateway_id = gateway.get('gatewayId')
        
        # Create log group name following AWS convention
        log_group_name = f"/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/{gateway_id}"
        
        # Create CloudWatch Logs client
        logs_client = boto3.client('logs', region_name=region)
        
        # Create the log group (if it doesn't exist)
        try:
            logs_client.create_log_group(logGroupName=log_group_name)
            logger.info(f"✅ Created log group: {log_group_name}")
        except logs_client.exceptions.ResourceAlreadyExistsException:
            logger.info(f"Log group already exists: {log_group_name}")
        except Exception as e:
            logger.warning(f"Could not create log group: {e}")
        
        # Configure log delivery using boto3 directly
        try:
            client = boto3.client('bedrock-agent-runtime', region_name=region)
            response = client.put_gateway_log_delivery_configuration(
                gatewayIdentifier=gateway_id,
                logType='APPLICATION_LOGS',
                logDestinationConfig={
                    'cloudWatchLogsConfig': {
                        'logGroupName': log_group_name
                    }
                }
            )
            
            logger.info("✅ Gateway logging configured successfully")
            logger.info(f"Logs will be available in: {log_group_name}")
            logger.info("Gateway metrics will be available in CloudWatch under 'Bedrock-AgentCore' namespace")
            return True
        except Exception as e:
            logger.warning(f"Could not configure log delivery: {e}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Failed to configure gateway logging: {str(e)}")
        logger.warning("Gateway will function but observability data won't be available")
        return False


def ensure_gateway_execution_role_permissions(
    gateway: Dict[str, Any],
    tools: List[Dict[str, Any]],
    neptune_runtime_arn: str,
    region: str,
    logger: logging.Logger,
) -> bool:
    """Ensure the Gateway role can be assumed and invoke its configured targets."""
    role_arn = gateway.get("roleArn")
    gateway_arn = gateway.get("gatewayArn")

    if not role_arn or not gateway_arn:
        logger.error("Gateway role ARN or gateway ARN is missing")
        return False

    role_name = role_arn.rsplit("/", 1)[-1]
    iam_client = boto3.client("iam")

    try:
        account_id = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
        role = iam_client.get_role(RoleName=role_name)["Role"]
        trust_policy = role["AssumeRolePolicyDocument"]
        statements = trust_policy.get("Statement", [])
        if isinstance(statements, dict):
            statements = [statements]
            trust_policy["Statement"] = statements

        expected_source_account = account_id
        trust_exists = any(
            statement.get("Effect") == "Allow"
            and "bedrock-agentcore.amazonaws.com"
            in (
                statement.get("Principal", {}).get("Service", [])
                if isinstance(statement.get("Principal", {}).get("Service", []), list)
                else [statement.get("Principal", {}).get("Service")]
            )
            and "sts:AssumeRole"
            in (
                statement.get("Action", [])
                if isinstance(statement.get("Action", []), list)
                else [statement.get("Action")]
            )
            and statement.get("Condition", {}).get("StringEquals", {}).get("aws:SourceAccount")
            == expected_source_account
            and any(
                fnmatchcase(gateway_arn, source_arn)
                for source_arn in (
                    statement.get("Condition", {}).get("ArnLike", {}).get("aws:SourceArn", [])
                    if isinstance(
                        statement.get("Condition", {}).get("ArnLike", {}).get("aws:SourceArn", []),
                        list,
                    )
                    else [statement.get("Condition", {}).get("ArnLike", {}).get("aws:SourceArn")]
                )
            )
            for statement in statements
        )

        if not trust_exists:
            statements.append(
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": expected_source_account},
                        "ArnLike": {"aws:SourceArn": gateway_arn},
                    },
                }
            )
            iam_client.update_assume_role_policy(
                RoleName=role_name,
                PolicyDocument=json.dumps(trust_policy),
            )
            logger.info("Added AgentCore trust for gateway execution role")

        lambda_arns = sorted({tool["lambda_arn"] for tool in tools if tool.get("lambda_arn")})
        if not lambda_arns or not neptune_runtime_arn:
            logger.error("Gateway target ARNs are not fully configured")
            return False

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="NetworkOperationsGatewayTargetInvocation",
            PolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "lambda:InvokeFunction",
                            "Resource": lambda_arns,
                        },
                        {
                            "Effect": "Allow",
                            "Action": "bedrock-agentcore:InvokeAgentRuntime",
                            "Resource": neptune_runtime_arn,
                        }
                    ],
                }
            ),
        )
        logger.info("Configured least-privilege invocation policy for gateway targets")
        return True

    except ClientError as error:
        logger.error("Failed to configure Gateway execution role: %s", error)
        return False


def get_tool_configurations(env: str, region: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    """
    Get tool configurations for all Lambda functions to be added to the gateway.
    
    This function defines the tools and their schemas. Add new tools here as you
    develop them.
    
    Args:
        env: Environment name (test/prod)
        region: AWS region
        logger: Logger instance
    
    Returns:
        List of tool configuration dictionaries
    """
    tools = []
    
    # Get Lambda function ARNs for this environment
    lambda_arns = get_lambda_target_arns(env)
    
    # PSR Lookup Tool
    logger.info("Adding PSR Lookup tool configuration...")
    tools.append({
        "name": "PSRLookupTarget",
        "lambda_arn": lambda_arns["psr_lookup"],
        "tool_schema": {
            "inlinePayload": [
                {
                    "name": "psr_lookup",
                    "description": "Check Priority Services Register (PSR) status for UK postcodes in the North West England electricity distribution network. Returns whether each postcode is registered on the PSR (vulnerable customers requiring special assistance during power outages).",
                    "inputSchema": {
                        "type": "object",
                        "description": "Parameters for PSR lookup",
                        "properties": {
                            "postcodes": {
                                "type": "array",
                                "description": "Array of UK postcodes to check (e.g., ['M1 1AA', 'L1 8JQ'])",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["postcodes"]
                    },
                    "outputSchema": {
                        "type": "object",
                        "description": "PSR lookup results",
                        "properties": {
                            "statusCode": {
                                "type": "integer",
                                "description": "HTTP status code"
                            },
                            "body": {
                                "type": "object",
                                "description": "Response body containing results or error",
                                "properties": {
                                    "results": {
                                        "type": "array",
                                        "description": "Array of PSR lookup results for each postcode",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "postcode": {
                                                    "type": "string",
                                                    "description": "The postcode that was queried"
                                                },
                                                "on_psr": {
                                                    "type": "boolean",
                                                    "description": "Whether the postcode is registered on the PSR"
                                                }
                                            },
                                            "required": ["postcode", "on_psr"]
                                        }
                                    },
                                    "error": {
                                        "type": "string",
                                        "description": "Error message"
                                    }
                                }
                            }
                        },
                        "required": ["statusCode", "body"]
                    }
                }
            ]
        }
    })
    
    # Workforce Router Tool
    logger.info("Adding Workforce Router tool configuration...")
    tools.append({
        "name": "WorkforceRouterTarget",
        "lambda_arn": lambda_arns["workforce_router"],
        "tool_schema": {
            "inlinePayload": [
                {
                    "name": "recommend_engineers",
                    "description": "Get engineer recommendations for a specific fault type in the electricity distribution network. Use this to find qualified engineers who can respond to network faults.",
                    "inputSchema": {
                        "type": "object",
                        "description": "Parameters for engineer recommendation",
                        "properties": {
                            "fault_type": {
                            "type": "string",
                            "description": "Type of fault requiring engineer dispatch"
                            },
                            "action": {
                            "type": "string",
                            "description": "Action to perform"
                            }
                        },
                        "required": ["action", "fault_type"]
                    },
                    "outputSchema": {
                        "type": "object",
                        "description": "Engineer recommendation results",
                        "properties": {
                            "statusCode": {
                                "type": "integer",
                                "description": "HTTP status code"
                            },
                            "body": {
                                "type": "object",
                                "description": "Response body",
                                "properties": {
                                    "status": {
                                        "type": "string",
                                        "description": "Response status"
                                    },
                                    "fault_type": {
                                        "type": "string",
                                        "description": "The fault type that was queried"
                                    },
                                    "required_skill": {
                                        "type": "string",
                                        "description": "The primary skill required for this fault type"
                                    },
                                    "recommendations": {
                                        "type": "array",
                                        "description": "Array of engineer recommendations",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "engineer_id": {
                                                    "type": "integer",
                                                    "description": "Internal engineer ID"
                                                },
                                                "employee_id": {
                                                    "type": "string",
                                                    "description": "Employee ID"
                                                },
                                                "name": {
                                                    "type": "string",
                                                    "description": "Engineer's full name"
                                                },
                                                "skills": {
                                                    "type": "array",
                                                    "description": "Engineer's skills relevant to this fault",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "skill_name": {
                                                                "type": "string",
                                                                "description": "Name of the skill"
                                                            },
                                                            "proficiency_level": {
                                                                "type": "string",
                                                                "description": "Proficiency level: 'lead engineer', 'certified', or 'trainee'"
                                                            }
                                                        },
                                                        "required": ["skill_name", "proficiency_level"]
                                                    }
                                                },
                                                "location": {
                                                    "type": "object",
                                                    "description": "Engineer's current location (optional)",
                                                    "properties": {
                                                        "latitude": {
                                                            "type": "number",
                                                            "description": "Latitude coordinate"
                                                        },
                                                        "longitude": {
                                                            "type": "number",
                                                            "description": "Longitude coordinate"
                                                        }
                                                    }
                                                },
                                                "availability_status": {
                                                    "type": "string",
                                                    "description": "Current availability status (always 'available' in recommendations)"
                                                }
                                            },
                                            "required": ["engineer_id", "employee_id", "name", "skills", "availability_status"]
                                        }
                                    },
                                    "total_available": {
                                        "type": "integer",
                                        "description": "Total number of available engineers returned"
                                    },
                                    "message": {
                                        "type": "string",
                                        "description": "Descriptive message (present when no engineers available or error)"
                                    },
                                    "error_type": {
                                        "type": "string",
                                        "description": "Error type (present when status is 'error')"
                                    }
                                },
                                "required": ["status"]
                            }
                        },
                        "required": ["statusCode", "body"]
                    }
                },
                {
                    "name": "assign_engineer",
                    "description": "Assign an available engineer to a fault by updating their status to 'on-job'",
                    "inputSchema": {
                        "type": "object",
                        "description": "Parameters for engineer assignment",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "Action to perform eg. 'assign_engineer'"
                            },
                            "engineer_id": {
                                "type": "integer",
                                "description": "Internal engineer ID from the recommendations list"
                            },
                            "fault_type": {
                                "type": "string",
                                "description": "Type of fault the engineer is being assigned to (transformer_failure, cable_fault, overhead_line_fault, circuit_breaker_fault, protection_device_fault, insulator_failure, substation_equipment_fault)"
                            }
                        },
                        "required": ["action", "engineer_id"]
                    },
                    "outputSchema": {
                        "type": "object",
                        "description": "Engineer assignment results",
                        "properties": {
                            "statusCode": {
                                "type": "integer",
                                "description": "HTTP status code"
                            },
                            "body": {
                                "type": "object",
                                "description": "Response body",
                                "properties": {
                                    "status": {
                                        "type": "string",
                                        "description": "Response status: 'success' or 'error'"
                                    },
                                    "engineer_id": {
                                        "type": "integer",
                                        "description": "Internal engineer ID (present on success)"
                                    },
                                    "employee_id": {
                                        "type": "string",
                                        "description": "Employee ID (present on success)"
                                    },
                                    "name": {
                                        "type": "string",
                                        "description": "Engineer's full name (present on success)"
                                    },
                                    "previous_status": {
                                        "type": "string",
                                        "description": "Previous availability status (present on success)"
                                    },
                                    "new_status": {
                                        "type": "string",
                                        "description": "New availability status (present on success)"
                                    },
                                    "updated_at": {
                                        "type": "string",
                                        "description": "Timestamp when status was updated (present on success)"
                                    },
                                    "error_type": {
                                        "type": "string",
                                        "description": "Error type (present when status is 'error')"
                                    },
                                    "message": {
                                        "type": "string",
                                        "description": "Descriptive error message (present when status is 'error')"
                                    }
                                },
                                "required": ["status"]
                            }
                        },
                        "required": ["statusCode", "body"]
                    }
                }
            ]
        }
    })

    # Postcode to Geo Info Tool
    logger.info("Adding Postcode To LatLong tool configuration...")
    tools.append({
        "name": "PostcodeToGeoTarget",
        "lambda_arn": lambda_arns["convert_postcode_to_latitude_and_longitude"],
        "tool_schema": {
            "inlinePayload": [
                {
                    "name": "convert_postcode_to_latitude_and_longitude",
                    "description": "Convert a UK postcode to geographic coordinates (latitude/longitude) and location information. Use this to get coordinates needed for weather forecasting or location-based queries.",
                    "inputSchema": {
                        "type": "object",
                        "description": "Parameters for retrieving the latitude and longitude of a given postcode",
                        "properties": {
                            "postcode": {
                                "type": "string",
                                "description": "UK postcode to convert (e.g., 'SW1A 1AA', 'M1 1AA')"
                            }
                        },
                        "required": ["postcode"]
                    },
                    "outputSchema": {
                        "type": "object",
                        "description": "Postcode geocoding results",
                        "properties": {
                            "statusCode": {
                                "type": "integer",
                                "description": "HTTP status code (200 for success, 400 for bad request, 404 for not found, 500 for error)"
                            },
                            "body": {
                                "type": "string",
                                "description": "JSON string containing the response data or error message"
                            }
                        },
                        "required": ["statusCode", "body"]
                    }
                }
            ]
        }
    })

    # Weather forecast Tool
    logger.info("Adding weather forecasting tool configuration...")
    tools.append({
        "name": "WeatherForecastTarget",
        "lambda_arn": lambda_arns["get_forecast_at_latlong"],
        "tool_schema": {
            "inlinePayload": [
                {
                    "name": "get_forecast_at_latlong",
                    "description": "Get the 7 day weather forecast for the given latitude and longitude to see if any adverse weather conditions are predicted in the area.",
                    "inputSchema": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                        "type": "number",
                        "description": "The latitude to use for obtaining the weather forecast in a specific location e.g. 81.5074"
                        },
                        "longitude": {
                        "type": "number",
                        "description": "The longitude to use for obtaining the weather forecast in a specific location e.g. -0.1278"
                        }
                    },
                    "required": [
                        "latitude",
                        "longitude"
                    ],
                    "description": "Parameters for retrieving the weather forecast at a given latitude and longitude."
                    }
                }
            ]
        }
    })
    
    # Add more tools here as you develop them
    # Example:
    # logger.info("Adding Neptune Query tool configuration...")
    # tools.append({
    #     "name": "NeptuneQueryTarget",
    #     "lambda_arn": lambda_arns["neptune_query"],
    #     "tool_schema": { ... }
    # })
    
    logger.info(f"Configured {len(tools)} tool(s)")
    return tools


def create_or_update_gateway_targets(
    gateway: Dict[str, Any],
    tools: List[Dict[str, Any]],
    gateway_client: GatewayClient,
    logger: logging.Logger
) -> bool:
    """
    Create or update gateway targets for all tools.
    
    This function is idempotent - it will update existing targets or create new ones.
    
    Args:
        gateway: Gateway details
        tools: List of tool configurations
        gateway_client: GatewayClient instance
        logger: Logger instance
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Configuring {len(tools)} tool(s) as gateway targets...")
        
        for tool in tools:
            logger.info(f"Adding target: {tool['name']}")
            
            target_payload = {
                "lambdaArn": tool['lambda_arn'],
                "toolSchema": tool['tool_schema']
            }
            
            try:
                target = gateway_client.create_mcp_gateway_target(
                    gateway=gateway,
                    name=tool['name'],
                    target_type="lambda",
                    target_payload=target_payload,
                    credentials=None  # Use Gateway IAM role
                )
                logger.info(f"✅ Target '{tool['name']}' configured successfully")
                
            except Exception as e:
                # If target already exists, this is expected and OK
                if "already exists" in str(e).lower() or "conflict" in str(e).lower():
                    logger.info(f"Target '{tool['name']}' already exists - skipping")
                else:
                    logger.error(f"Failed to create target '{tool['name']}': {e}")
                    return False
        
        logger.info("✅ All targets configured successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure gateway targets: {e}")
        return False


def create_or_update_neptune_mcp_target(
    gateway: Dict[str, Any],
    target_configuration: Dict[str, Any],
    gateway_client: GatewayClient,
    logger: logging.Logger,
) -> bool:
    """Create or update the Neptune MCP Runtime target using the control-plane API."""
    control_client = gateway_client.client
    gateway_id = gateway["gatewayId"]

    try:
        target_id = None
        next_token = None
        while True:
            response = control_client.list_gateway_targets(
                gatewayIdentifier=gateway_id,
                **({"nextToken": next_token} if next_token else {}),
            )
            existing_target = next(
                (
                    target
                    for target in response.get("items", [])
                    if target.get("name") == target_configuration["name"]
                ),
                None,
            )
            if existing_target:
                target_id = existing_target["targetId"]
                break
            next_token = response.get("nextToken")
            if not next_token:
                break

        request = {
            "gatewayIdentifier": gateway_id,
            "name": target_configuration["name"],
            "description": target_configuration["description"],
            "targetConfiguration": target_configuration["targetConfiguration"],
            "credentialProviderConfigurations": (
                target_configuration["credentialProviderConfigurations"]
            ),
            "metadataConfiguration": target_configuration["metadataConfiguration"],
        }

        if target_id:
            logger.info("Updating Neptune MCP Runtime target: %s", target_id)
            control_client.update_gateway_target(targetId=target_id, **request)
        else:
            logger.info("Creating Neptune MCP Runtime target")
            target_id = control_client.create_gateway_target(**request)["targetId"]

        return wait_for_gateway_target_ready(
            control_client,
            gateway_id,
            target_id,
            logger,
        )
    except ClientError as error:
        logger.error("Failed to configure Neptune MCP Runtime target: %s", error)
        return False


def wait_for_gateway_target_ready(
    control_client: Any,
    gateway_id: str,
    target_id: str,
    logger: logging.Logger,
    timeout_seconds: int = 300,
    poll_seconds: int = 5,
) -> bool:
    """Wait for AgentCore to synchronize the target and expose its MCP tools."""
    terminal_failures = {
        "FAILED",
        "UPDATE_UNSUCCESSFUL",
        "SYNCHRONIZE_UNSUCCESSFUL",
    }
    elapsed = 0

    while elapsed <= timeout_seconds:
        response = control_client.get_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id,
        )
        status = response.get("status")
        if status == "READY":
            logger.info("Neptune MCP Runtime target is READY")
            return True
        if status in terminal_failures:
            logger.error(
                "Neptune MCP Runtime target entered %s: %s",
                status,
                response.get("statusReasons", []),
            )
            return False

        logger.info("Neptune MCP Runtime target status: %s", status)
        time.sleep(poll_seconds)
        elapsed += poll_seconds

    logger.error("Timed out waiting for Neptune MCP Runtime target to become READY")
    return False


def deploy_agentcore_gateway(env: str, force_recreate: bool, logger: logging.Logger) -> Dict[str, Any]:
    """
    Deploy or update the network operations gateway.
    
    This function is idempotent - it will reuse existing gateway if found,
    or create a new one if needed.
    
    Args:
        env: Environment name (test/prod)
        force_recreate: If True, delete and recreate gateway
        logger: Logger instance
    
    Returns:
        Dictionary with deployment results
    """
    logger.info(f"Deploying network operations gateway to {env} environment...")
    
    region = get_region_for_environment(env)
    gateway_name = get_gateway_name(env)
    
    deployment_result = {
        "success": False,
        "gateway_url": None,
        "gateway_id": None,
        "cognito_info": None,
        "logging_configured": False,
        "tools_configured": 0,
        "neptune_target_configured": False,
        "error_message": None
    }
    
    try:
        # Initialize the GatewayClient
        gateway_client = GatewayClient(region_name=region)
        
        # Check for existing gateway
        existing_gateway = find_existing_gateway(gateway_name, region, logger)
        
        if existing_gateway and force_recreate:
            logger.info("Force recreate requested - deleting existing gateway")
            if not delete_gateway(existing_gateway['gatewayId'], region, logger):
                deployment_result["error_message"] = "Failed to delete existing gateway"
                return deployment_result
            existing_gateway = None
        
        # Create gateway if it doesn't exist
        if existing_gateway:
            logger.info("Using existing gateway")
            gateway = existing_gateway
            
            # Note: We can't easily retrieve Cognito info for existing gateway
            # User will need to check AWS Console or previous deployment logs
            logger.warning("Using existing gateway - Cognito credentials not available")
            logger.warning("Check previous deployment logs or AWS Console for authentication details")
            
        else:
            logger.info("Creating new gateway with OAuth authorization...")
            
            # Create OAuth authorization server with Cognito
            logger.info("Creating OAuth authorization server with Cognito...")
            cognito_response = gateway_client.create_oauth_authorizer_with_cognito(gateway_name)
            logger.info("✅ OAuth authorization server created")
            
            # Create the MCP Gateway
            logger.info("Creating MCP Gateway...")
            gateway = gateway_client.create_mcp_gateway(
                name=gateway_name,
                role_arn=None,  # Auto-create execution role
                authorizer_config=cognito_response["authorizer_config"],
                enable_semantic_search=True
            )
            logger.info("✅ Gateway created")
            
            # Fix IAM permissions
            gateway_client.fix_iam_permissions(gateway)
            logger.info("⏳ Waiting 30s for IAM propagation...")
            time.sleep(30)
            logger.info("✅ IAM permissions configured")
            
            # Store Cognito info
            # Handle different possible response structures
            client_info = cognito_response.get("client_info", {})
            deployment_result["cognito_info"] = {
                "user_pool_id": client_info.get("user_pool_id"),
                "client_id": client_info.get("client_id"),
                "discovery_url": client_info.get("discovery_url") or client_info.get("issuer"),
                "token_endpoint": client_info.get("token_endpoint")
            }
        
        # Configure gateway observability (logging and metrics)
        logger.info("=" * 40)
        logger.info("Configuring Gateway Observability")
        logger.info("=" * 40)
        logging_configured = configure_gateway_logging(gateway, region, logger)
        deployment_result["logging_configured"] = logging_configured
        
        if not logging_configured:
            logger.warning("⚠️  Gateway logging configuration failed - continuing with target setup")
        
        # Get tool configurations
        logger.info("=" * 40)
        logger.info("Configuring Gateway Targets")
        logger.info("=" * 40)
        tools = get_tool_configurations(env, region, logger)
        neptune_runtime = get_neptune_mcp_runtime_configuration(env)
        neptune_target = get_neptune_mcp_target_configuration(env, region)
        
        if not tools:
            logger.error("No tools configured - check Lambda function deployment")
            deployment_result["error_message"] = "No tools available to configure"
            return deployment_result

        if not ensure_gateway_execution_role_permissions(
            gateway,
            tools,
            neptune_runtime["arn"],
            region,
            logger,
        ):
            deployment_result["error_message"] = "Failed to configure Gateway execution role"
            return deployment_result
        
        # Create or update gateway targets
        if not create_or_update_gateway_targets(gateway, tools, gateway_client, logger):
            deployment_result["error_message"] = "Failed to configure gateway targets"
            return deployment_result

        if not create_or_update_neptune_mcp_target(
            gateway,
            neptune_target,
            gateway_client,
            logger,
        ):
            deployment_result["error_message"] = "Failed to configure Neptune MCP Runtime target"
            return deployment_result
        
        deployment_result["tools_configured"] = len(tools)
        deployment_result["neptune_target_configured"] = True
        deployment_result["gateway_url"] = gateway["gatewayUrl"]
        deployment_result["gateway_id"] = gateway["gatewayId"]
        deployment_result["success"] = True
        
        logger.info("✅ Gateway deployment completed successfully")
        logger.info(f"Gateway URL: {gateway['gatewayUrl']}")
        logger.info(f"Gateway ID: {gateway['gatewayId']}")
        
        if deployment_result["cognito_info"]:
            logger.info(f"Cognito User Pool ID: {deployment_result['cognito_info']['user_pool_id']}")
            logger.info(f"Cognito Client ID: {deployment_result['cognito_info']['client_id']}")
            logger.info(f"Cognito Discovery URL: {deployment_result['cognito_info']['discovery_url']}")
        
        return deployment_result
        
    except Exception as e:
        error_msg = f"Gateway deployment failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        deployment_result["error_message"] = error_msg
        return deployment_result


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Deploy AgentCore Gateway for Network Operations Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --env test
  %(prog)s --env prod --verbose
  %(prog)s --env test --force-recreate
        """
    )
    
    parser.add_argument(
        '--env', '--environment',
        choices=['test', 'prod'],
        default='test',
        help='Deployment environment (default: test)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging mode'
    )
    
    parser.add_argument(
        '--force-recreate',
        action='store_true',
        help='Force recreation of gateway (delete and recreate)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the deployment script."""
    args = parse_arguments()
    
    # Set up logging
    logger = setup_logging(args.verbose)
    
    # Log script start
    logger.info("=" * 60)
    logger.info("Network Operations Gateway Deployment Started")
    logger.info("=" * 60)
    logger.info(f"Environment: {args.env}")
    logger.info(f"Target Region: {get_region_for_environment(args.env)}")
    logger.info(f"Force Recreate: {args.force_recreate}")
    logger.info(f"Verbose Mode: {args.verbose}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    try:
        # Validate prerequisites
        if not validate_prerequisites(logger):
            logger.error("Prerequisite validation failed")
            sys.exit(1)
        
        # Deploy the gateway
        logger.info("=" * 40)
        logger.info("Deploying Gateway")
        logger.info("=" * 40)
        
        result = deploy_agentcore_gateway(args.env, args.force_recreate, logger)
        
        if not result["success"]:
            logger.error("Gateway deployment failed")
            logger.error(f"Error: {result['error_message']}")
            sys.exit(1)
        
        # Log successful deployment
        logger.info("=" * 60)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Environment: {args.env}")
        logger.info(f"Region: {get_region_for_environment(args.env)}")
        logger.info(f"Gateway URL: {result['gateway_url']}")
        logger.info(f"Gateway ID: {result['gateway_id']}")
        logger.info(f"Tools Configured: {result['tools_configured']}")
        logger.info(
            "Neptune MCP Runtime Target Configured: %s",
            "Yes" if result["neptune_target_configured"] else "No",
        )
        logger.info(f"Logging Configured: {'Yes' if result['logging_configured'] else 'No'}")
        
        if result.get('cognito_info'):
            logger.info("")
            logger.info("Authentication Details:")
            logger.info(f"  User Pool ID: {result['cognito_info']['user_pool_id']}")
            logger.info(f"  Client ID: {result['cognito_info']['client_id']}")
            logger.info(f"  Discovery URL: {result['cognito_info']['discovery_url']}")
            logger.info(f"  Token Endpoint: {result['cognito_info']['token_endpoint']}")
        
        logger.info("=" * 60)
        logger.info("✅ Deployment completed successfully!")
        
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        logger.error("Run with --verbose for more detailed error information")
        sys.exit(1)


if __name__ == "__main__":
    main()
