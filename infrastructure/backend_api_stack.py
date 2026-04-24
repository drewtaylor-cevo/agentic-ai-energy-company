"""Phase 3 CDK stack — Backend API (Lambda + HTTP API v2).

Reads AgentCore runtime ARN from SSM (written by AgentCoreStack) to avoid
hard CloudFormation export dependencies between stacks (Pitfall 5).
"""
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from infrastructure.constructs.backend_api import BackendApiConstruct


class BackendApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Read AgentCore runtime ARN from SSM (D-07: avoids CfnOutput export lock).
        # value_for_string_parameter returns a CloudFormation dynamic reference
        # token (resolves at deploy time, NOT synth time).
        agent_runtime_arn = ssm.StringParameter.value_for_string_parameter(
            self, "/customer-tariff/agent-runtime-arn"
        )

        backend = BackendApiConstruct(
            self,
            "BackendApi",
            agent_runtime_arn=agent_runtime_arn,
        )

        CfnOutput(self, "ApiEndpoint", value=backend.api_endpoint)
