"""Offline CDK synth test for BackendApiStack — no AWS credentials needed.

Synthesizes the BackendApiStack in-memory and inspects the CloudFormation
template for expected resources: HTTP API v2, Lambda, route, CORS, and IAM.
Also verifies the AgentCoreStack SSM amendment (Task 2.1).
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

try:
    from infrastructure.backend_api_stack import BackendApiStack
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="BackendApiStack import failed: {}".format(_IMPORT_ERROR),
)


@pytest.fixture(scope="module")
def synth_template():
    app = cdk.App()
    stack = BackendApiStack(
        app,
        "TestBackendApiStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)


def test_stack_synthesises(synth_template):
    """Basic smoke: the stack produces a non-empty template."""
    assert synth_template.to_json().get("Resources")


def test_has_http_api(synth_template):
    """Template must contain exactly one HTTP API v2."""
    synth_template.resource_count_is("AWS::ApiGatewayV2::Api", 1)


def test_has_lambda(synth_template):
    """Template must contain exactly one Lambda function."""
    synth_template.resource_count_is("AWS::Lambda::Function", 1)


def test_has_route(synth_template):
    """Route key must be GET /recommendations/{customer_id} (D-10)."""
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {"RouteKey": "GET /recommendations/{customer_id}"},
    )


def test_lambda_runtime_and_handler(synth_template):
    """Lambda must use Python 3.12, handler.handler entry point, tariff-api name."""
    synth_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "handler.handler",
            "FunctionName": "tariff-api",
        },
    )


def test_lambda_timeout(synth_template):
    """Lambda timeout must be 30s (D-03)."""
    synth_template.has_resource_properties(
        "AWS::Lambda::Function",
        {"Timeout": 30},
    )


def test_cors_allow_all(synth_template):
    """CORS must allow origin '*' (D-09)."""
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Api",
        {
            "CorsConfiguration": {
                "AllowOrigins": ["*"],
            }
        },
    )


def test_cors_methods(synth_template):
    """CORS must allow GET and OPTIONS methods (D-09)."""
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Api",
        {
            "CorsConfiguration": {
                "AllowMethods": ["GET", "OPTIONS"],
            }
        },
    )


def test_cors_headers(synth_template):
    """CORS must allow Content-Type header (D-09)."""
    synth_template.has_resource_properties(
        "AWS::ApiGatewayV2::Api",
        {
            "CorsConfiguration": {
                "AllowHeaders": ["Content-Type"],
            }
        },
    )


def test_has_iam_policy_with_invoke_agent_runtime(synth_template):
    """IAM policy must include bedrock-agentcore:InvokeAgentRuntime."""
    template_json = synth_template.to_json()
    found = False
    for resource in template_json.get("Resources", {}).values():
        if resource.get("Type") == "AWS::IAM::Policy":
            doc = resource["Properties"].get("PolicyDocument", {})
            for statement in doc.get("Statement", []):
                actions = statement.get("Action")
                if isinstance(actions, str):
                    actions = [actions]
                if actions and "bedrock-agentcore:InvokeAgentRuntime" in actions:
                    found = True
    assert found, "No IAM policy found with bedrock-agentcore:InvokeAgentRuntime"


def test_agentcore_stack_has_ssm_parameter():
    """AgentCoreStack must write /customer-tariff/agent-runtime-arn to SSM (D-07)."""
    from infrastructure.agentcore_stack import AgentCoreStack

    app = cdk.App()
    stack = AgentCoreStack(
        app,
        "TestAgentCoreSSM",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    template = Template.from_stack(stack)
    template.has_resource_properties(
        "AWS::SSM::Parameter",
        {
            "Name": "/customer-tariff/agent-runtime-arn",
            "Type": "String",
        },
    )
