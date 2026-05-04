"""AgentCore Runtime construct — deploys the Strands agent container.

Uses the CDK L2 alpha construct to build the Docker image from agent/,
push to a CDK-managed ECR repo, and create the AgentCore Runtime resource.
IAM is scoped to lambda:InvokeFunction on the ToolsLambda ARN and
bedrock:InvokeModel for Claude model access.

Phase 15 WF-01: accepts optional memory_id kwarg; when provided, adds
MEMORY_ID env var to the runtime and grants Memory API permissions.

The L2 construct auto-creates the execution IAM role with ECR pull,
CloudWatch Logs, and X-Ray permissions. We add lambda:InvokeFunction
and bedrock:InvokeModel via add_to_role_policy().
"""
import aws_cdk as cdk
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from constructs import Construct

from aws_cdk import aws_bedrock_agentcore_alpha as agentcore


class AgentRuntimeConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        tools_lambda_arn: str,
        memory_id: str = "",
    ) -> None:
        super().__init__(scope, construct_id)

        artifact = agentcore.AgentRuntimeArtifact.from_asset(
            "agent",
            platform=ecr_assets.Platform.LINUX_ARM64,
        )

        env_vars = {
            "TOOLS_LAMBDA_ARN": tools_lambda_arn,
            "AWS_REGION": cdk.Stack.of(self).region,
        }
        # Phase 15 WF-01: inject MEMORY_ID when Memory resource is provisioned.
        if memory_id:
            env_vars["MEMORY_ID"] = memory_id

        self._runtime = agentcore.Runtime(
            self,
            "TariffAgentRuntime",
            runtime_name="tariff_agent",
            agent_runtime_artifact=artifact,
            environment_variables=env_vars,
            description="Strands agent: Green + Cheapest tariff recommendations",
        )

        stack = cdk.Stack.of(self)

        # Bedrock model invocation — Claude 3.7 Sonnet
        # Cross-region inference profile (us.*) may route to any US region,
        # so we allow all US regions for foundation-model access.
        self._runtime.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:{}:inference-profile/*".format(stack.account),
                    "arn:aws:bedrock:*:{}:*".format(stack.account),
                ],
            )
        )

        # Lambda tool invocation — scoped to ToolsLambda ARN only
        self._runtime.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[tools_lambda_arn],
            )
        )

        # Phase 15 WF-01: Memory API permissions for follow-up email workflow.
        # Grants CreateEvent (store recommendation context), ListEvents (retrieve
        # prior turn), and RetrieveMemoryRecords (query short-term events).
        if memory_id:
            self._runtime.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "bedrock-agentcore:CreateEvent",
                        "bedrock-agentcore:ListEvents",
                        "bedrock-agentcore:RetrieveMemoryRecords",
                        "bedrock-agentcore:GetMemory",
                    ],
                    resources=["*"],
                )
            )

    @property
    def agent_runtime_arn(self) -> str:
        return self._runtime.agent_runtime_arn

    @property
    def agent_runtime_id(self) -> str:
        return self._runtime.agent_runtime_id
