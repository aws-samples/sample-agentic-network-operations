#!/usr/bin/env python3
"""
Network Operations Agent Deployment Script

This script deploys the network operations agent to AWS using the bedrock_agentcore_starter_toolkit
with Docker and ECR deployment (container-based).

PREREQUISITES:
1. Install required packages:
   pip install bedrock-agentcore-starter-toolkit==0.3.0 boto3==1.43.54

2. Configure AWS credentials (one of):
   - AWS CLI: aws configure
   - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
   - IAM role (if running on EC2)

3. Ensure Docker is installed and running (for container builds)

4. AgentCore Gateway must be deployed first. It exposes the Neptune MCP Runtime
   and Lambda tools through one authenticated MCP endpoint.

NOTE: ***IAM ROLE****
    The execution role for AgentCore runtime will be auto-configured the first time this script is run.
    It won't have enough permissions to complete its actions, so you will need to add them or pre-create
    the role and set it in .bedrock_agentcore.yaml

    The network operations agent needs permissions to:
    - cognito-idp:DescribeUserPool
    - cognito-idp:DescribeUserPoolClient
    - bedrock-agentcore-control:GetGateway
    - bedrock:InvokeModel (for Claude Sonnet 4.5)

USAGE:
    # Deploy to test environment (us-east-1) - default
    python deploy_agent.py --env test

    # Deploy to production environment (us-west-2)
    python deploy_agent.py --env prod

    # Deploy with verbose logging
    python deploy_agent.py --env test --verbose

WHAT THIS SCRIPT DOES:
1. Validates AWS credentials and prerequisites
2. Validates config.{env}.json has the AgentCore Gateway endpoint
3. Builds Docker container with agent code
4. Pushes container to ECR (auto-created)
5. Deploys agent to AgentCore Runtime in specified environment

The script will output the deployed agent ARN upon successful completion.
"""

import argparse
import logging
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import boto3
from boto3.session import Session
from botocore.exceptions import NoCredentialsError, ClientError, ProfileNotFound
from bedrock_agentcore_starter_toolkit import Runtime


# Environment-specific AWS regions
TEST_REGION = "us-east-1"
PROD_REGION = "us-west-2"

ENTRYPOINT = "src/main.py"


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('network_operations_agent_deploy')
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


def resolve_environment_placeholder(value: str) -> str:
    """Resolve a complete ${ENVIRONMENT_VARIABLE} deployment placeholder."""
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        variable_name = value[2:-1]
        resolved = os.getenv(variable_name)
        if not resolved:
            raise ValueError(
                f"Environment variable {variable_name} is required for deployment"
            )
        return resolved
    return value


def load_deployment_config(env: str) -> Dict[str, Any]:
    """Load and resolve the environment-specific agent configuration."""
    config_path = Path(f"config.{env}.json")
    with open(config_path, 'r') as f:
        config = json.load(f)

    gateway_config = config.get("agentcore_gateway", {})
    config["agentcore_gateway"] = {
        field: resolve_environment_placeholder(value)
        for field, value in gateway_config.items()
    }
    return config


def validate_prerequisites(logger: logging.Logger, env: str) -> bool:
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

    # Check if config file exists
    config_path = Path(f"config.{env}.json")
    if not config_path.exists():
        logger.error(f"Configuration file not found: config.{env}.json")
        logger.error("This file must contain the AgentCore Gateway configuration")
        return False

    # Validate agent configuration
    try:
        config = load_deployment_config(env)

        # Check for required top-level fields
        required_fields = ['environment', 'aws_region', 'agentcore_gateway']
        for field in required_fields:
            if field not in config:
                logger.error(f"Configuration missing required field: {field}")
                return False

        # Validate environment matches
        if config['environment'] != env:
            logger.error(f"Configuration environment '{config['environment']}' doesn't match deployment environment '{env}'")
            return False

        # Validate region matches
        region = get_region_for_environment(env)
        if config['aws_region'] != region:
            logger.error(f"Configuration region '{config['aws_region']}' doesn't match expected region '{region}'")
            return False

        # Validate AgentCore Gateway config
        gateway_config = config['agentcore_gateway']
        required_gateway_fields = ['gateway_id', 'endpoint']
        for field in required_gateway_fields:
            if field not in gateway_config:
                logger.error(f"AgentCore Gateway configuration missing required field: {field}")
                return False

            value = gateway_config[field]
            if not value or value.startswith('REPLACE_WITH'):
                logger.error(f"AgentCore Gateway {field} not configured: {value}")
                logger.error("Deploy the AgentCore Gateway first and set its configuration environment variables")
                return False

        if not gateway_config['endpoint'].startswith('https://'):
            logger.error(f"AgentCore Gateway endpoint must be HTTPS: {gateway_config['endpoint']}")
            return False

        logger.info(f"Configuration validated for environment: {env}")
        logger.info(f"  AgentCore Gateway: {gateway_config['gateway_id']}")

        # Verify the endpoints match the target environment region
        if f".{region}." not in gateway_config['endpoint']:
            logger.warning(f"⚠️  AgentCore Gateway endpoint region doesn't match target region {region}")
            logger.warning(f"   Endpoint: {gateway_config['endpoint']}")

    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        return False

    return True


def validate_pyproject_toml(logger: logging.Logger) -> bool:
    """Validate that pyproject.toml exists for the agent."""
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        logger.error("pyproject.toml not found")
        logger.error("This file is required for dependency management during Docker build")
        return False

    logger.info("✅ pyproject.toml found")
    return True


def configure_execution_role_permissions(env: str, region: str, logger: logging.Logger) -> bool:
    """
    Configure IAM permissions for the agent execution role.

    The agent needs permissions to:
    - Access Cognito user pools for OAuth token acquisition
    - Call GetGateway to discover gateway configuration

    Args:
        env: Environment (test/prod)
        region: AWS region
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    logger.info("Configuring execution role IAM permissions...")

    try:
        # Load config to get the Gateway ID.
        config = load_deployment_config(env)
        gateway_id = config['agentcore_gateway']['gateway_id']

        # Get AWS account ID
        session = Session()
        sts_client = session.client('sts')
        account_id = sts_client.get_caller_identity()['Account']

        # Construct execution role name (follows AgentCore SDK naming convention)
        role_name = f"AmazonBedrockAgentCoreSDKRuntime-{region}-0f901c07f3"

        # Get the gateway's Cognito user pool ID by calling GetGateway
        agentcore_client = session.client('bedrock-agentcore-control', region_name=region)
        try:
            gateway_response = agentcore_client.get_gateway(gatewayIdentifier=gateway_id)
            discovery_url = gateway_response['authorizerConfiguration']['customJWTAuthorizer']['discoveryUrl']

            # Extract user pool ID from discovery URL
            # Format: https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration
            url_parts = discovery_url.split('/')
            # user_pool_id is after the domain, before .well-known
            gateway_user_pool_id = url_parts[3]
            logger.info(f"Discovered gateway user pool: {gateway_user_pool_id}")
        except Exception as e:
            logger.warning(f"Could not discover gateway user pool ID: {e}")
            logger.warning("Cannot grant Cognito access without the Gateway user pool")
            gateway_user_pool_id = None

        # Build IAM policy document
        policy_statements = [
            {
                "Effect": "Allow",
                "Action": "bedrock-agentcore:GetGateway",
                "Resource": f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/{gateway_id}"
            }
        ]

        # The agent retrieves the Gateway's client secret at runtime.
        if gateway_user_pool_id:
            policy_statements.insert(
                0,
                {
                    "Effect": "Allow",
                    "Action": [
                        "cognito-idp:DescribeUserPoolClient",
                    ],
                    "Resource": (
                        f"arn:aws:cognito-idp:{region}:{account_id}:"
                        f"userpool/{gateway_user_pool_id}"
                    ),
                },
            )

        policy_document = {
            "Version": "2012-10-17",
            "Statement": policy_statements
        }

        # Apply the policy to the execution role
        iam_client = session.client('iam')
        policy_name = "NetworkOperationsAgentCognitoAccess"

        logger.info(f"Applying IAM policy '{policy_name}' to role '{role_name}'...")
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document)
        )

        logger.info("✅ IAM permissions configured successfully")
        if gateway_user_pool_id:
            logger.info(f"   - Cognito access for Gateway: {gateway_user_pool_id}")
        logger.info(f"   - Gateway access: {gateway_id}")

        return True

    except Exception as e:
        logger.error(f"Failed to configure IAM permissions: {e}")
        logger.error("You may need to add these permissions manually")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


def deploy_network_operations_agent(env: str, logger: logging.Logger) -> Dict[str, Any]:
    """Deploy the network operations agent using Docker and ECR."""
    logger.info(f"Deploying network operations agent to {env} environment...")

    region = get_region_for_environment(env)
    agent_name = f"network_operations_agent_{env}"

    deployment_result = {
        "success": False,
        "agent_arn": None,
        "agent_id": None,
        "error_message": None,
        "iam_configured": False
    }

    try:
        # Initialize AgentCore Runtime
        logger.info("Initializing AgentCore Runtime...")
        agentcore_runtime = Runtime()
        gateway_config = load_deployment_config(env)["agentcore_gateway"]

        # Configure the agent with Docker/ECR deployment
        logger.info("Configuring agent with Docker/ECR deployment...")
        config_response = agentcore_runtime.configure(
            entrypoint=ENTRYPOINT,
            auto_create_execution_role=True,
            auto_create_ecr=True,  # This enables Docker/ECR deployment
            requirements_file="pyproject.toml",  # Use pyproject.toml for dependencies
            region=region,
            agent_name=agent_name
        )
        logger.info("✅ Agent configuration completed")

        # Launch the agent (this will build Docker image and push to ECR)
        logger.info("Launching agent deployment...")
        logger.info("This will build a Docker container and push to ECR - may take several minutes...")

        launch_result = agentcore_runtime.launch(
            env_vars={
                "AGENTCORE_GATEWAY_ID": gateway_config["gateway_id"],
                "AGENTCORE_GATEWAY_ENDPOINT": gateway_config["endpoint"],
            }
        )

        deployment_result["agent_arn"] = launch_result.agent_arn
        deployment_result["agent_id"] = launch_result.agent_id

        logger.info("✅ Agent deployment completed")
        logger.info(f"Agent ARN: {launch_result.agent_arn}")
        logger.info(f"Agent ID: {launch_result.agent_id}")

        # Wait for agent to be ready
        logger.info("Checking agent status...")
        status_response = agentcore_runtime.status()
        status = status_response.endpoint['status']
        logger.info(f"Initial status: {status}")

        end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        max_wait_time = 600  # 10 minutes
        wait_time = 0

        while status not in end_status and wait_time < max_wait_time:
            logger.info(f"Status: {status} - waiting...")
            time.sleep(30)
            wait_time += 30
            status_response = agentcore_runtime.status()
            status = status_response.endpoint['status']

        if status == 'READY':
            logger.info("✅ Agent is READY!")
            deployment_result["success"] = True

            # Configure IAM permissions for the execution role
            logger.info("")
            logger.info("=" * 60)
            logger.info("Configuring IAM Permissions")
            logger.info("=" * 60)
            iam_success = configure_execution_role_permissions(env, region, logger)
            deployment_result["iam_configured"] = iam_success

            if not iam_success:
                logger.warning("⚠️  IAM permissions were not configured automatically")
                logger.warning("   The agent may fail to authenticate with Cognito")
                logger.warning("   Please add the required permissions manually")
        else:
            logger.error(f"❌ Agent deployment failed with status: {status}")
            deployment_result["error_message"] = f"Agent status: {status}"
            return deployment_result

        return deployment_result

    except Exception as e:
        error_msg = f"Agent deployment failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        deployment_result["error_message"] = error_msg
        return deployment_result


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Deploy Network Operations Agent with Docker/ECR',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --env test
  %(prog)s --env prod --verbose
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

    return parser.parse_args()


def main():
    """Main entry point for the deployment script."""
    args = parse_arguments()

    # Set up logging
    logger = setup_logging(args.verbose)

    # Log script start
    logger.info("=" * 60)
    logger.info("Network Operations Agent Deployment Started")
    logger.info("=" * 60)
    logger.info(f"Environment: {args.env}")
    logger.info(f"Target Region: {get_region_for_environment(args.env)}")
    logger.info(f"Verbose Mode: {args.verbose}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    try:
        # Validate prerequisites
        if not validate_prerequisites(logger, args.env):
            logger.error("Prerequisite validation failed")
            sys.exit(1)

        # Validate pyproject.toml exists
        if not validate_pyproject_toml(logger):
            logger.error("pyproject.toml validation failed")
            sys.exit(1)

        # Deploy the network operations agent
        logger.info("=" * 40)
        logger.info("Deploying Network Operations Agent")
        logger.info("=" * 40)

        agent_result = deploy_network_operations_agent(args.env, logger)

        if not agent_result["success"]:
            logger.error("Agent deployment failed")
            logger.error(f"Error: {agent_result['error_message']}")
            sys.exit(1)

        # Log successful deployment
        logger.info("=" * 60)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Environment: {args.env}")
        logger.info(f"Region: {get_region_for_environment(args.env)}")
        logger.info("Agent Deployment:")
        logger.info(f"  Agent ARN: {agent_result.get('agent_arn', 'N/A')}")
        logger.info(f"  Agent ID: {agent_result.get('agent_id', 'N/A')}")
        logger.info("")
        logger.info("IAM Configuration:")
        if agent_result.get('iam_configured', False):
            logger.info("  ✅ Execution role permissions configured automatically")
        else:
            logger.info("  ⚠️  Execution role permissions NOT configured")
            logger.info("     You may need to add Cognito permissions manually")
        logger.info("")
        logger.info("✅ Deployment completed successfully!")
        logger.info("")
        logger.info("Next Steps:")
        logger.info("1. Test the agent with a sample query:")
        logger.info("   agentcore invoke '{\"prompt\": \"What substations feed Southport?\"}'")
        logger.info("")
        logger.info("2. Check logs:")
        logger.info(f"   CloudWatch Logs: /aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/{agent_result.get('agent_id', 'AGENT_ID')}")
        logger.info("")
        if not agent_result.get('iam_configured', False):
            logger.info("3. Grant IAM permissions to the execution role:")
            logger.info("   The agent needs:")
            logger.info("   - cognito-idp:DescribeUserPoolClient")
            logger.info("   - bedrock-agentcore:GetGateway")
            logger.info("   - bedrock:InvokeModel (for Claude Sonnet 4.5)")
            logger.info("")
            logger.info("4. Update config file with agent ARN if needed for orchestration")
        else:
            logger.info("3. Update config file with agent ARN if needed for orchestration")

    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        logger.error("Run with --verbose for more detailed error information")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
