"""Phase 2 CDK stack — AgentCore Runtime for the Strands agent.

Reads ToolsLambda ARN from SSM (written by FoundationStack) to avoid
hard CloudFormation export dependencies between stacks (Pitfall 5).
"""
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from infrastructure.constructs.agent_runtime import AgentRuntimeConstruct


class AgentCoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Read ToolsLambda ARN from SSM — decoupled from FoundationStack
        tools_lambda_arn = ssm.StringParameter.value_for_string_parameter(
            self, "/customer-tariff/tools-lambda-arn"
        )

        runtime = AgentRuntimeConstruct(
            self,
            "AgentRuntime",
            tools_lambda_arn=tools_lambda_arn,
        )

        CfnOutput(self, "AgentRuntimeArn", value=runtime.agent_runtime_arn)
        CfnOutput(self, "AgentRuntimeId", value=runtime.agent_runtime_id)

        # Cross-stack wiring: write AgentRuntime ARN to SSM so BackendApiStack
        # can read it without a hard CloudFormation export dependency (Pitfall 5,
        # mirrors the FoundationStack -> AgentCoreStack pattern from Phase 1->2).
        # D-07. Lifecycle: parameter is managed by this stack; cdk destroy
        # CustomerTariffAgent removes it, which is correct — if the runtime is
        # gone, the stored ARN is stale.
        ssm.StringParameter(
            self,
            "AgentRuntimeArnParam",
            parameter_name="/customer-tariff/agent-runtime-arn",
            string_value=runtime.agent_runtime_arn,
            description="AgentCore runtime ARN for BackendApiStack cross-stack wiring",
        )
