"""Phase 2 CDK stack — AgentCore Runtime for the Strands agent.

Reads ToolsLambda ARN from SSM (written by FoundationStack) to avoid
hard CloudFormation export dependencies between stacks (Pitfall 5).

Phase 15 WF-01: adds AgentCore Memory resource (short-term only, 12h TTL)
for follow-up email workflow. Memory ID written to SSM and passed to the
runtime as MEMORY_ID env var.
"""
from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from aws_cdk import aws_bedrock_agentcore_alpha as agentcore

from infrastructure.constructs.agent_runtime import AgentRuntimeConstruct


class AgentCoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Read ToolsLambda ARN from SSM — decoupled from FoundationStack
        tools_lambda_arn = ssm.StringParameter.value_for_string_parameter(
            self, "/customer-tariff/tools-lambda-arn"
        )

        # Phase 15 WF-01: short-term only Memory (LD-3).
        # No memory_strategies — short-term event storage only, no long-term
        # extraction. 7-day TTL (minimum allowed by CDK L2 construct).
        # Short-term events are the actual recall mechanism; the expiration
        # duration governs long-term memory retention. For demo purposes,
        # `scripts/memory-reset.sh` runs at T-24h and T-2h per DEMO-RUNBOOK.
        memory = agentcore.Memory(
            self,
            "TariffAgentMemory",
            memory_name="tariff_agent_memory",
            description="Short-term session memory for follow-up email workflow (WF-01)",
            expiration_duration=Duration.days(7),
        )

        runtime = AgentRuntimeConstruct(
            self,
            "AgentRuntime",
            tools_lambda_arn=tools_lambda_arn,
            memory_id=memory.memory_id,
        )

        CfnOutput(self, "AgentRuntimeArn", value=runtime.agent_runtime_arn)
        CfnOutput(self, "AgentRuntimeId", value=runtime.agent_runtime_id)
        CfnOutput(self, "MemoryId", value=memory.memory_id)

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

        # Phase 15 WF-01: write Memory ID to SSM for cross-stack reference.
        ssm.StringParameter(
            self,
            "MemoryIdParam",
            parameter_name="/customer-tariff/memory-id",
            string_value=memory.memory_id,
            description="AgentCore Memory ID for follow-up email workflow (WF-01)",
        )
