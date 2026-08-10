#!/usr/bin/env python3
"""
Neptune MCP Runtime Deployment Script

This script deploys the AWS Labs Amazon Neptune MCP Server as an AgentCore
Runtime target behind the Network Operations AgentCore Gateway.

PREREQUISITES:
1. Install required packages:
   pip install bedrock-agentcore-starter-toolkit==0.3.0 boto3==1.43.54

2. Configure AWS credentials (one of):
   - AWS CLI: aws configure
   - Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
   - IAM role (if running on EC2)

3. Neptune Analytics graph must be deployed and available

USAGE:
    # Deploy to test environment (us-east-1)
    python agentcore/neptune_mcp_runtime/deploy_neptune_mcp_runtime.py --env test

    # Deploy to production environment (us-west-2)
    python agentcore/neptune_mcp_runtime/deploy_neptune_mcp_runtime.py --env prod

    # Deploy with verbose logging
    python agentcore/neptune_mcp_runtime/deploy_neptune_mcp_runtime.py --env test --verbose

WHAT THIS SCRIPT DOES:
1. Validates AWS credentials and prerequisites
2. Builds Docker image with AWS Labs Neptune MCP server
3. Pushes Docker image to ECR
5. Configures environment variables for Neptune Analytics connectivity
6. Configures CloudWatch logging

ENVIRONMENTS:
- test: Deploys to us-east-1 region
- prod: Deploys to us-west-2 region

The script will output the runtime endpoint and ARN used by the Gateway target.
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import NoCredentialsError, ClientError, ProfileNotFound
from bedrock_agentcore_starter_toolkit import Runtime


# Environment-specific configuration
ENVIRONMENTS = {
    "test": {
        "region": "us-east-1",
        "runtime_name": "neptune_mcp_runtime_test",
        "log_level": "INFO",
    },
    "prod": {
        "region": "us-west-2",
        "runtime_name": "neptune_mcp_runtime_prod",
        "log_level": "ERROR",
    }
}


def get_environment_config(env: str) -> Dict[str, Any]:
    """Load the graph identifier from deployment-time environment configuration."""
    graph_id = os.getenv("NEPTUNE_GRAPH_ID")
    if not graph_id:
        raise ValueError(
            "NEPTUNE_GRAPH_ID must be set before deploying the Neptune MCP Runtime"
        )

    return {
        **ENVIRONMENTS[env],
        "neptune_graph_id": graph_id,
    }

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger('neptune_mcp_deploy')
    logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


def validate_prerequisites(env_config: Dict[str, Any], logger: logging.Logger) -> bool:
    """Validate all prerequisites for deployment."""
    logger.info("Validating prerequisites...")
    
    # Validate AWS credentials
    try:
        session = boto3.Session()
        sts_client = session.client('sts')
        identity = sts_client.get_caller_identity()
        
        logger.info("✅ AWS credentials validated")
        logger.info(f"Account ID: {identity.get('Account', 'Unknown')}")
        logger.info(f"User/Role ARN: {identity.get('Arn', 'Unknown')}")
        
    except (NoCredentialsError, ProfileNotFound, ClientError) as e:
        logger.error(f"❌ AWS credentials validation failed: {e}")
        return False
    
    # Validate Neptune Analytics graph exists
    try:
        neptune_client = boto3.client('neptune-graph', region_name=env_config['region'])
        response = neptune_client.get_graph(graphIdentifier=env_config['neptune_graph_id'])
        
        graph_status = response.get('status', 'UNKNOWN')
        logger.info(f"✅ Neptune Analytics graph found: {env_config['neptune_graph_id']}")
        logger.info(f"Graph status: {graph_status}")
        
        if graph_status != 'AVAILABLE':
            logger.warning(f"⚠️  Graph status is {graph_status}, not AVAILABLE")
            logger.warning("Deployment may fail if graph is not ready")
        
    except ClientError as e:
        logger.error(f"❌ Neptune Analytics graph validation failed: {e}")
        logger.error(f"Graph ID: {env_config['neptune_graph_id']}")
        return False
    
    return True


def deploy_neptune_mcp_runtime(env: str, logger: logging.Logger) -> Dict[str, Any]:
    """
    Deploy the Neptune MCP Runtime for Gateway IAM authentication.
    
    Args:
        env: Environment name (test/prod)
        logger: Logger instance
    
    Returns:
        Dictionary with deployment results
    """
    logger.info(f"Deploying Neptune MCP Runtime to {env} environment...")
    
    env_config = get_environment_config(env)
    region = env_config['region']
    
    deployment_result = {
        "success": False,
        "agent_arn": None,
        "agent_id": None,
        "endpoint_url": None,
        "error_message": None
    }
    
    try:
        # Change to the neptune_mcp_runtime directory
        original_dir = os.getcwd()
        runtime_dir = os.path.join(original_dir, 'agentcore', 'neptune_mcp_runtime')
        
        # Check if we're already in the runtime directory
        if not os.path.exists('main.py'):
            if os.path.exists(runtime_dir):
                os.chdir(runtime_dir)
                logger.info(f"Changed to runtime directory: {runtime_dir}")
            else:
                raise Exception(f"Runtime directory not found: {runtime_dir}")
        
        # Initialize Runtime
        logger.info("Initializing AgentCore Runtime...")
        agentcore_runtime = Runtime()
        
        # Configure the runtime
        logger.info("Configuring AgentCore Runtime...")
        logger.info("This will build and push Docker image - may take several minutes...")
        
        response = agentcore_runtime.configure(
            entrypoint="main.py",
            auto_create_execution_role=True,
            auto_create_ecr=True,
            requirements_file="requirements.txt",
            region=region,
            protocol="MCP",
            agent_name=env_config['runtime_name']
        )
        
        logger.info("✅ Runtime configuration completed")
        
        logger.info("Passing Neptune runtime configuration at launch")
        logger.info(f"  NEPTUNE_GRAPH_ID: {env_config['neptune_graph_id']}")
        logger.info(f"  AWS_REGION: {region}")
        logger.info(f"  LOG_LEVEL: {env_config['log_level']}")
        
        # Launch the runtime
        logger.info("Launching Neptune MCP Runtime...")
        logger.info("This may take several minutes...")
        
        launch_result = agentcore_runtime.launch(
            env_vars={
                "NEPTUNE_GRAPH_ID": env_config["neptune_graph_id"],
                "AWS_REGION": region,
                "LOG_LEVEL": env_config["log_level"],
            }
        )
        logger.info("✅ Launch initiated")
        logger.info(f"Agent ARN: {launch_result.agent_arn}")
        logger.info(f"Agent ID: {launch_result.agent_id}")
        
        logger.info("✅ Launch initiated")
        logger.info(f"Agent ARN: {launch_result.agent_arn}")
        logger.info(f"Agent ID: {launch_result.agent_id}")
        
        # Wait for runtime to be ready
        logger.info("Checking runtime status...")
        import time
        
        max_wait_time = 600  # 10 minutes
        check_interval = 10  # 10 seconds
        elapsed_time = 0
        
        end_statuses = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        
        while elapsed_time < max_wait_time:
            status_response = agentcore_runtime.status()
            status = status_response.endpoint.get('status', 'UNKNOWN')
            
            logger.info(f"Status: {status} (elapsed: {elapsed_time}s)")
            
            if status in end_statuses:
                break
            
            time.sleep(check_interval)
            elapsed_time += check_interval
        
        if status == 'READY':
            logger.info("✅ Neptune MCP Runtime is READY!")
            
            # Get endpoint URL
            endpoint_url = status_response.endpoint.get('endpointUrl')
            
            deployment_result["success"] = True
            deployment_result["agent_arn"] = launch_result.agent_arn
            deployment_result["agent_id"] = launch_result.agent_id
            deployment_result["endpoint_url"] = endpoint_url
            
        else:
            error_msg = f"Runtime status: {status} (not READY)"
            logger.error(f"❌ {error_msg}")
            deployment_result["error_message"] = error_msg
            deployment_result["agent_arn"] = launch_result.agent_arn
            deployment_result["agent_id"] = launch_result.agent_id
        
        return deployment_result
        
    except Exception as e:
        error_msg = f"Deployment failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        deployment_result["error_message"] = error_msg
        return deployment_result
    finally:
        # Restore original directory
        if 'original_dir' in locals():
            os.chdir(original_dir)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Deploy Neptune MCP Runtime to AgentCore',
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
    logger.info("Neptune MCP Runtime Deployment Started")
    logger.info("=" * 60)
    logger.info(f"Environment: {args.env}")
    try:
        # Get environment configuration
        env_config = get_environment_config(args.env)
        logger.info(f"Target Region: {env_config['region']}")
        logger.info(f"Neptune Graph ID: {env_config['neptune_graph_id']}")
        logger.info(f"Runtime Name: {env_config['runtime_name']}")
        logger.info(f"Verbose Mode: {args.verbose}")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        
        # Validate prerequisites
        logger.info("=" * 40)
        logger.info("Validating Prerequisites")
        logger.info("=" * 40)
        
        if not validate_prerequisites(env_config, logger):
            logger.error("❌ Prerequisite validation failed")
            sys.exit(1)
        
        # Deploy the runtime
        logger.info("=" * 40)
        logger.info("Deploying Neptune MCP Runtime")
        logger.info("=" * 40)
        
        result = deploy_neptune_mcp_runtime(args.env, logger)
        
        if not result["success"]:
            logger.error("❌ Neptune MCP Runtime deployment failed")
            logger.error(f"Error: {result['error_message']}")
            if result.get('agent_arn'):
                logger.info(f"Agent ARN: {result['agent_arn']}")
                logger.info(f"Agent ID: {result['agent_id']}")
                logger.info("Check CloudWatch logs for more details")
            sys.exit(1)
        
        # Log successful deployment
        logger.info("=" * 60)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Environment: {args.env}")
        logger.info(f"Region: {env_config['region']}")
        logger.info(f"Neptune Graph ID: {env_config['neptune_graph_id']}")
        logger.info(f"Runtime Name: {env_config['runtime_name']}")
        logger.info("")
        logger.info("Runtime Details:")
        logger.info(f"  Agent ARN: {result['agent_arn']}")
        logger.info(f"  Agent ID: {result['agent_id']}")
        logger.info(f"  Endpoint URL: {result['endpoint_url']}")
        logger.info("")
        logger.info("Authentication Details:")
        logger.info("  AgentCore Gateway invokes this runtime with IAM/SigV4")
        logger.info("  Direct client authorization is not configured")
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Deployment completed successfully!")
        logger.info("")
        logger.info("Next Steps:")
        logger.info("1. Deploy or update the AgentCore Gateway target for this runtime")
        logger.info("2. Test the topology tools through the AgentCore Gateway")
        logger.info("3. Monitor CloudWatch logs for runtime activity")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Deployment interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Deployment failed: {str(e)}")
        logger.error("Run with --verbose for more detailed error information")
        sys.exit(1)


if __name__ == "__main__":
    main()
