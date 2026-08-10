#!/usr/bin/env python3
"""
Orchestration Agent Deployment Script

This script deploys the orchestration agent to AWS using the bedrock_agentcore_starter_toolkit
with Docker and ECR deployment (container-based).

PREREQUISITES:
1. Install required packages:
   pip install bedrock-agentcore-starter-toolkit==0.3.0 boto3==1.43.54

2. Configure AWS credentials (one of):
   - AWS CLI: aws configure
   - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
   - IAM role (if running on EC2)

3. Ensure Docker is installed and running (for container builds)

4. Both intelligent charging agent and inverter configurator agent must be deployed first
   (their ARNs are needed in agent_config.json)

NOTE: ***IAM ROLE****
    The execution role for AgentCore runtime will be auto-configured the first time this script is run.
    It won't have enough permissions to complete its actions, so you will need to add them or pre-create 
    the role and set it in .bedrock_agentcore.yaml
    
    The orchestration agent needs permissions to invoke other AgentCore agents:
    - bedrock-agentcore:InvokeAgent

USAGE:
    # Deploy to test environment (us-east-1) - default
    python deploy_agent.py --env test

    # Deploy to production environment (us-west-2)
    python deploy_agent.py --env prod

    # Deploy with verbose logging
    python deploy_agent.py --env test --verbose

WHAT THIS SCRIPT DOES:
1. Validates AWS credentials and prerequisites
2. Validates agent_config.json has correct agent ARNs
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
    
    logger = logging.getLogger('orchestration_agent_deploy')
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
    
    # Check if agent_config.json exists
    agent_config_path = Path("src/agent_config.json")
    if not agent_config_path.exists():
        logger.error("Agent configuration file not found at src/agent_config.json")
        logger.error("This file must contain ARNs for intelligent charging and inverter configurator agents")
        return False
    
    # Validate agent configuration
    try:
        with open(agent_config_path, 'r') as f:
            full_config = json.load(f)
        
        # Check for environments structure
        if 'environments' not in full_config:
            logger.error("Agent configuration missing 'environments' section")
            logger.error("Configuration should have 'environments' with 'test' and 'prod' keys")
            return False
        
        # Determine which environment to validate based on deployment target
        region = get_region_for_environment(env)
        config_env = 'prod' if region == 'us-west-2' else 'test'
        
        if config_env not in full_config['environments']:
            logger.error(f"Agent configuration missing '{config_env}' environment")
            return False
        
        agent_config = full_config['environments'][config_env]
        
        required_fields = ['intelligent_charging_agent_arn', 'inverter_configurator_agent_arn']
        for field in required_fields:
            if field not in agent_config:
                logger.error(f"Agent configuration for '{config_env}' missing required field: {field}")
                return False
            
            arn = agent_config[field]
            if not arn or arn.startswith('arn:aws:bedrock-agentcore:') is False:
                logger.error(f"Invalid ARN for {field} in '{config_env}': {arn}")
                logger.error("Deploy the intelligent charging and inverter configurator agents first")
                return False
        
        logger.info(f"Agent configuration validated for environment: {config_env}")
        logger.info(f"  Intelligent Charging Agent: {agent_config['intelligent_charging_agent_arn']}")
        logger.info(f"  Inverter Configurator Agent: {agent_config['inverter_configurator_agent_arn']}")
        
        # Verify the ARNs match the target environment region
        for field in required_fields:
            arn = agent_config[field]
            if f":{region}:" not in arn:
                logger.warning(f"⚠️  {field} ARN region doesn't match target region {region}")
                logger.warning(f"   ARN: {arn}")
                logger.warning("   This may cause cross-region invocation issues")
        
    except Exception as e:
        logger.error(f"Failed to validate agent configuration: {e}")
        return False
    
    return True


def deploy_orchestration_agent(env: str, logger: logging.Logger) -> Dict[str, Any]:
    """Deploy the orchestration agent using Docker and ECR."""
    logger.info(f"Deploying orchestration agent to {env} environment...")
    
    region = get_region_for_environment(env)
    agent_name = f"orchestrationagent_{env}"
    
    deployment_result = {
        "success": False,
        "agent_arn": None,
        "agent_id": None,
        "error_message": None
    }
    
    try:
        # Initialize AgentCore Runtime
        logger.info("Initializing AgentCore Runtime...")
        agentcore_runtime = Runtime()
        
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
        
        launch_result = agentcore_runtime.launch()
        
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
        description='Deploy Orchestration Agent with Docker/ECR',
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
    logger.info("Orchestration Agent Deployment Started")
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
        
        # Deploy the orchestration agent
        logger.info("=" * 40)
        logger.info("Deploying Orchestration Agent")
        logger.info("=" * 40)
        
        agent_result = deploy_orchestration_agent(args.env, logger)
        
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
        logger.info("Orchestrated Agents:")
        logger.info("  This agent coordinates:")
        logger.info("  1. Intelligent Charging Agent (decision making)")
        logger.info("  2. Inverter Configurator Agent (implementation)")
        logger.info("=" * 60)
        logger.info("✅ Deployment completed successfully!")
        logger.info("")
        logger.info("Next Steps:")
        logger.info("1. Update EventBridge rule to trigger this orchestration agent")
        logger.info("   (instead of the intelligent charging agent directly)")
        logger.info("")
        logger.info("2. Test the orchestration workflow:")
        logger.info("   agentcore invoke '{\"trigger\": \"manual_test\"}'")
        logger.info("")
        logger.info("3. Check logs:")
        logger.info(f"   CloudWatch Logs: /aws/vendedlogs/bedrock-agentcore/runtime/APPLICATION_LOGS/{agent_result.get('agent_id', 'AGENT_ID')}")
        logger.info("")
        logger.info("4. Grant IAM permissions to the execution role:")
        logger.info("   The orchestration agent needs bedrock-agentcore:InvokeAgent permission")
        logger.info("   to call the intelligent charging and inverter configurator agents")
        
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        logger.error("Run with --verbose for more detailed error information")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
