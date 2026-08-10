"""Regression tests for the Gateway-only agent architecture."""

import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from botocore.session import get_session
from botocore.validate import ParamValidator


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
AGENT_MAIN_PATH = REPOSITORY_ROOT / "agentcore/network_operations_agent/src/main.py"
GATEWAY_DEPLOY_PATH = REPOSITORY_ROOT / "agentcore/deploy_agentcore_gateway.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


agent_main = load_module("network_operations_agent_main", AGENT_MAIN_PATH)
gateway_deploy = load_module("network_operations_gateway_deploy", GATEWAY_DEPLOY_PATH)


def configure_deployment_environment(monkeypatch):
    monkeypatch.setenv("AGENTCORE_GATEWAY_ID", "netops-gateway-test")
    monkeypatch.setenv(
        "AGENTCORE_GATEWAY_ENDPOINT",
        "https://netops-gateway-test.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
    )
    monkeypatch.setenv(
        "NETOPS_TEST_NEPTUNE_MCP_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/neptune-test",
    )


def test_agent_configuration_only_requires_gateway(monkeypatch):
    configure_deployment_environment(monkeypatch)
    config = agent_main.AgentConfig.load_from_file(
        REPOSITORY_ROOT / "agentcore/network_operations_agent/config.test.json"
    )

    assert config.agentcore_gateway.gateway_id
    assert not hasattr(config, "neptune_mcp")


def test_network_agent_discovers_tools_from_gateway_only(monkeypatch):
    configure_deployment_environment(monkeypatch)
    config = agent_main.AgentConfig.load_from_file(
        REPOSITORY_ROOT / "agentcore/network_operations_agent/config.test.json"
    )
    gateway_tools = Mock()
    gateway_tools.get_tools.return_value = [Mock(tool_name="get_graph_schema")]

    with (
        patch.object(agent_main, "OAuthTokenManager") as oauth_manager,
        patch.object(
            agent_main,
            "AgentCoreGatewayTools",
            return_value=gateway_tools,
        ) as gateway_tools_class,
        patch.object(agent_main, "BedrockModel"),
        patch.object(agent_main, "Agent") as strands_agent,
    ):
        agent = agent_main.NetworkOperationsAgent(config)

    gateway_tools_class.assert_called_once_with(oauth_manager.return_value, config)
    gateway_tools.initialize_client.assert_called_once()
    gateway_tools.get_tools.assert_called_once()
    assert not hasattr(agent, "neptune_tools")
    assert strands_agent.call_args.kwargs["tools"] == gateway_tools.get_tools.return_value


def test_neptune_runtime_target_uses_gateway_iam_and_sessions(monkeypatch):
    configure_deployment_environment(monkeypatch)
    target = gateway_deploy.get_neptune_mcp_target_configuration("test", "us-east-1")
    runtime_arn = gateway_deploy.get_neptune_mcp_runtime_configuration("test")["arn"]
    endpoint = target["targetConfiguration"]["mcp"]["mcpServer"]["endpoint"]

    assert target["name"] == "NeptuneMCPRuntimeTarget"
    assert "arn%3Aaws%3Abedrock-agentcore" in endpoint
    assert endpoint.endswith("qualifier=DEFAULT")
    assert runtime_arn not in endpoint
    assert target["credentialProviderConfigurations"] == [
        {
            "credentialProviderType": "GATEWAY_IAM_ROLE",
            "credentialProvider": {
                "iamCredentialProvider": {
                    "service": "bedrock-agentcore",
                    "region": "us-east-1",
                }
            },
        }
    ]
    assert target["metadataConfiguration"] == {
        "allowedRequestHeaders": ["Mcp-Session-Id"],
        "allowedResponseHeaders": ["Mcp-Session-Id"],
    }

    request = {
        "gatewayIdentifier": "gateway-123",
        "name": target["name"],
        "description": target["description"],
        "targetConfiguration": target["targetConfiguration"],
        "credentialProviderConfigurations": target["credentialProviderConfigurations"],
        "metadataConfiguration": target["metadataConfiguration"],
    }
    service_model = get_session().get_service_model("bedrock-agentcore-control")
    validation_report = ParamValidator().validate(
        request,
        service_model.operation_model("CreateGatewayTarget").input_shape,
    ).generate_report()
    assert not validation_report, validation_report


def test_existing_neptune_runtime_target_is_updated(monkeypatch):
    configure_deployment_environment(monkeypatch)
    target = gateway_deploy.get_neptune_mcp_target_configuration("test", "us-east-1")
    control_client = Mock()
    control_client.list_gateway_targets.return_value = {
        "items": [{"name": target["name"], "targetId": "target-123"}]
    }
    control_client.get_gateway_target.return_value = {"status": "READY"}
    gateway_client = SimpleNamespace(client=control_client)

    configured = gateway_deploy.create_or_update_neptune_mcp_target(
        {"gatewayId": "gateway-123"},
        target,
        gateway_client,
        logging.getLogger(__name__),
    )

    assert configured is True
    control_client.update_gateway_target.assert_called_once()
    assert control_client.update_gateway_target.call_args.kwargs["targetId"] == "target-123"
    control_client.create_gateway_target.assert_not_called()
