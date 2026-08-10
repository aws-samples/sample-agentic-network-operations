#!/usr/bin/env python3
"""
Local development script for Network Operations Agent.

This script allows testing the agent locally before deploying to AgentCore Runtime.
It loads configuration, initializes the agent, and runs example queries to verify
functionality.

Usage:
    # Use default config (config.test.json)
    python test_local.py
    
    # Use specific config file
    AGENT_CONFIG=config.dev.json python test_local.py
    
    # Run with custom AWS region
    AWS_REGION=us-west-2 python test_local.py
"""

import os
import sys
import logging
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from main import NetworkOperationsAgent, AgentConfig


def setup_logging(level: str = "INFO") -> None:
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_configuration() -> AgentConfig:
    """
    Load agent configuration from file.
    
    Returns:
        AgentConfig instance
        
    Raises:
        SystemExit: If configuration loading fails
    """
    logger = logging.getLogger(__name__)
    
    # Get config path from environment or use default
    config_path = os.environ.get('AGENT_CONFIG', 'config.test.json')
    logger.info(f"Loading configuration from: {config_path}")
    
    try:
        config = AgentConfig.load_from_file(config_path)
        return config
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        logger.error("Please create a configuration file or set AGENT_CONFIG environment variable")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        logger.error("Please check your configuration file for missing or invalid fields")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)
        sys.exit(1)


def initialize_agent(config: AgentConfig) -> NetworkOperationsAgent:
    """
    Initialize the Network Operations Agent.
    
    Args:
        config: Agent configuration
        
    Returns:
        Initialized NetworkOperationsAgent instance
        
    Raises:
        SystemExit: If agent initialization fails
    """
    logger = logging.getLogger(__name__)
    
    logger.info("\n" + "="*80)
    logger.info("Initializing Network Operations Agent...")
    logger.info("="*80 + "\n")
    
    try:
        agent = NetworkOperationsAgent(config)
        return agent
    except RuntimeError as e:
        logger.error(f"Failed to initialize agent: {e}")
        logger.error("Please check your configuration and AWS credentials")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during agent initialization: {e}", exc_info=True)
        sys.exit(1)


async def run_example_queries(agent: NetworkOperationsAgent) -> None:
    """
    Run example queries to test agent functionality.
    
    Args:
        agent: Initialized NetworkOperationsAgent instance
    """
    logger = logging.getLogger(__name__)
    
    # Define example queries
    example_queries = [
        {
            "title": "Single Substation Failure Impact",
            "query": "If Southport primary substation fails, how many PSR customers are affected?"
        },
        {
            "title": "Multi-Substation Backfeed Recommendation",
            "query": "The Southport and Wigan primary substations have failed. Which primary substation should I backfeed from to get the most people on the PSR register back on supply?"
        }
    ]
    
    # Run each query
    for i, example in enumerate(example_queries, 1):
        logger.info("\n" + "="*80)
        logger.info(f"Example Query {i}: {example['title']}")
        logger.info("="*80)
        logger.info("-"*80 + "\n")
        
        # Print progress indicator
        print(f"\n🔄 Processing query {i}/{len(example_queries)}: {example['title']}")
        print("⏳ Agent is thinking and using tools... (this may take 30-60 seconds)\n")
        sys.stdout.flush()
        
        try:
            print(f"\n{'='*80}")
            print(f"Response:")
            print(f"{'='*80}")
            
            # Stream the response
            async for chunk in agent.query_stream(example['query']):
                print(chunk, end='', flush=True)
            
            print(f"\n{'='*80}\n")
            sys.stdout.flush()
            
            logger.info("-"*80)
            logger.info("✅ Query completed successfully")
            
        except RuntimeError as e:
            logger.error(f"❌ Query failed: {e}")
            print(f"\n❌ Query {i} failed: {e}\n")
            sys.stdout.flush()
            logger.error("Continuing with next query...")
            
        except Exception as e:
            logger.error(f"❌ Unexpected error during query: {e}", exc_info=True)
            print(f"\n❌ Unexpected error in query {i}: {e}\n")
            sys.stdout.flush()
            logger.error("Continuing with next query...")


def main() -> None:
    """Main entry point for local testing script."""
    logger = logging.getLogger(__name__)
    
    # Set up logging
    log_level = os.environ.get('LOG_LEVEL', 'INFO')
    setup_logging(log_level)
    
    print("\n" + "="*80)
    print("Network Operations Agent - Local Development Testing")
    print("="*80 + "\n")
    sys.stdout.flush()
    
    logger.info("="*80)
    logger.info("Network Operations Agent - Local Development Testing")
    logger.info("="*80)
    
    # Load configuration
    print("📋 Loading configuration...")
    sys.stdout.flush()
    config = load_configuration()
    print(f"✅ Configuration loaded: {config.environment} environment, {config.aws_region} region\n")
    sys.stdout.flush()
    
    # Initialize agent
    print("🔧 Initializing Network Operations Agent...")
    print("   This includes:")
    print("   - OAuth token acquisition for AgentCore Gateway")
    print("   - Gateway MCP client initialization and tool discovery")
    print("   - Bedrock model setup (Claude Sonnet 4.5)")
    print("   ⏳ Please wait... (this may take 10-15 seconds)\n")
    sys.stdout.flush()
    
    agent = initialize_agent(config)
    
    print("✅ Agent initialized successfully!")
    print(f"   - AgentCore Gateway tools: Connected")
    print("   - Network topology tools are routed through Gateway")
    print(f"\n{'='*80}\n")
    sys.stdout.flush()
    
    # Run example queries
    print("🚀 Running example queries...")
    print("   Note: Each query may take 30-60 seconds as the agent:")
    print("   - Analyzes the question")
    print("   - Uses Gateway tools for topology and customer data")
    print("   - Synthesizes recommendations\n")
    sys.stdout.flush()
    
    import asyncio
    asyncio.run(run_example_queries(agent))
    
    # Summary
    print("\n" + "="*80)
    print("✅ Local testing complete!")
    print("="*80)
    print("\nTo run custom queries, use:")
    print("  python -c \"")
    print("  import sys, asyncio")
    print("  from pathlib import Path")
    print("  sys.path.insert(0, str(Path.cwd() / 'src'))")
    print("  from main import NetworkOperationsAgent, AgentConfig")
    print("  config = AgentConfig.load_from_file('config.test.json')")
    print("  agent = NetworkOperationsAgent(config)")
    print("  async def query():")
    print("      async for chunk in agent.query_stream('Your question here'):")
    print("          print(chunk, end='', flush=True)")
    print("  asyncio.run(query())")
    print("  \"")
    print()
    sys.stdout.flush()
    
    logger.info("\n" + "="*80)
    logger.info("Local testing complete")
    logger.info("="*80)


if __name__ == "__main__":
    main()
