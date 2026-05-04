"""Phase 3 construct — Backend API Lambda + API Gateway HTTP API v2.

Builds the API Lambda (api_lambda/ asset, Python 3.12, 30s timeout per D-03),
a HTTP API v2 with allow-all CORS (D-09), the route GET /recommendations/{customer_id}
(D-10) bound to the Lambda via HttpLambdaIntegration, and an IAM policy scoped
to bedrock-agentcore:InvokeAgentRuntime on the specific runtime ARN (RESEARCH.md Q6).

The AgentCore runtime ARN is passed in as a kwarg (CDK token from
ssm.StringParameter.value_for_string_parameter in BackendApiStack). CloudFormation
resolves the token at deploy time — no AWS creds required at synth (Pattern 5).

NOTE: The Lambda runtime's built-in boto3 predates the bedrock-agentcore service.
We bundle boto3>=1.42.0 via BundlingOptions so the Lambda has the service model.
"""
import aws_cdk as cdk
from aws_cdk import BundlingOptions, Duration
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integ
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class BackendApiConstruct(Construct):
    """API Lambda fronted by a HTTP API v2 with allow-all CORS."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        agent_runtime_arn: str,
    ) -> None:
        super().__init__(scope, construct_id)

        # Lambda function — api_lambda/ asset, Python 3.12, 30s timeout (D-03).
        # handler="handler.handler" refers to api_lambda/handler.py :: def handler
        # (RESEARCH.md Pitfall 7 — module.function mismatch is a common trap).
        #
        # The Lambda runtime's bundled boto3 is too old for bedrock-agentcore.
        # BundlingOptions pip-installs boto3>=1.42.0 into the asset zip so the
        # service model is available at runtime.
        fn = lambda_.Function(
            self,
            "TariffApiLambda",
            function_name="tariff-api",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(
                "api_lambda",
                bundling=BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output"
                        " && cp -au . /asset-output",
                    ],
                ),
            ),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "AGENT_RUNTIME_ARN": agent_runtime_arn,
                "LOG_LEVEL": "INFO",
            },
            description="Phase 3: proxies GET /recommendations/{customer_id} to AgentCore",
        )

        # IAM — scoped to InvokeAgentRuntime on the specific runtime ARN (Q6).
        # No grant_* helper exists for bedrock-agentcore; hand-write the
        # PolicyStatement following the agent_runtime.py pattern.
        #
        # The actual IAM resource checked by invoke_agent_runtime is the
        # runtime-endpoint sub-resource:
        #   arn:aws:bedrock-agentcore:{region}:{account}:runtime/{id}/runtime-endpoint/DEFAULT
        # We need both the runtime ARN and the sub-resource path.
        fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[
                    agent_runtime_arn,
                    cdk.Fn.join("/", [agent_runtime_arn, "*"]),
                ],
            )
        )

        # D-11 (Phase 7): read the `-c demo_pc=N` CDK context flag.
        # Absent → 0 (PC off, zero billing). Present → cast to int, validate.
        # Invalid values (non-numeric, negative) fail at synth time — cheap
        # to catch, never reaches CloudFormation (Pitfall 2).
        raw_pc = self.node.try_get_context("demo_pc")
        if raw_pc is None:
            demo_pc = 0
        else:
            try:
                demo_pc = int(raw_pc)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid -c demo_pc value: {raw_pc!r}. "
                    "Must be a non-negative integer."
                ) from exc
            if demo_pc < 0:
                raise ValueError(
                    f"Invalid -c demo_pc value: {demo_pc}. Must be >= 0."
                )

        # D-09/D-10 (Phase 7): alias ALWAYS created (whether PC is on or off).
        # Tracks fn.current_version by default — CDK auto-publishes a new
        # immutable Lambda version on each code change; the alias rolls
        # forward automatically on each `cdk deploy`.
        # D-11: provisioned_concurrent_executions kwarg attached ONLY when
        # demo_pc > 0. Default deploys remain zero-cost. Alias ARN is stable
        # across PC-on/PC-off deploys — Phase 10 freeze-surface critical.
        if demo_pc > 0:
            live_alias = fn.add_alias("live", provisioned_concurrent_executions=demo_pc)
        else:
            live_alias = fn.add_alias("live")

        # HTTP API v2 with allow-all CORS (D-09).
        api = apigwv2.HttpApi(
            self,
            "TariffApi",
            api_name="customer-tariff-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[
                    apigwv2.CorsHttpMethod.GET,
                    apigwv2.CorsHttpMethod.OPTIONS,
                ],
                allow_headers=["Content-Type"],
            ),
        )

        # Route: GET /recommendations/{customer_id} (D-10).
        api.add_routes(
            path="/recommendations/{customer_id}",
            methods=[apigwv2.HttpMethod.GET],
            integration=integ.HttpLambdaIntegration("RecoIntegration", live_alias),
        )

        # Phase 15 WF-01: follow-up email route.
        api.add_routes(
            path="/recommendations/{customer_id}/follow-up",
            methods=[apigwv2.HttpMethod.GET],
            integration=integ.HttpLambdaIntegration("FollowUpIntegration", live_alias),
        )

        self._api_endpoint = api.url

    @property
    def api_endpoint(self) -> str:
        """API endpoint URL (includes trailing slash)."""
        return self._api_endpoint
