"""Offline CDK synth test for AgentCoreStack — no AWS credentials needed.

Synthesizes the AgentCoreStack in-memory and inspects the CloudFormation
template for expected resources and IAM policies.

Requires the aws-cdk.aws-bedrock-agentcore-alpha package to be installed.
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

try:
    from infrastructure.agentcore_stack import AgentCoreStack
    _CAN_IMPORT = True
    _IMPORT_ERROR = ""
except ImportError as e:
    _CAN_IMPORT = False
    _IMPORT_ERROR = str(e)

pytestmark = pytest.mark.skipif(
    not _CAN_IMPORT,
    reason="AgentCoreStack import failed: {}".format(_IMPORT_ERROR),
)


@pytest.fixture(scope="module")
def synth_template():
    app = cdk.App()
    stack = AgentCoreStack(
        app,
        "TestAgentCoreStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)


def test_stack_synthesises(synth_template):
    """Basic smoke: the stack produces a non-empty template."""
    assert synth_template.to_json().get("Resources")


def test_has_agentcore_runtime(synth_template):
    """Template must contain an AgentCore Runtime resource."""
    synth_template.resource_count_is("AWS::BedrockAgentCore::Runtime", 1)


def test_has_iam_role(synth_template):
    """Template must contain an IAM execution role for the runtime."""
    synth_template.resource_count_is("AWS::IAM::Role", 1)


def test_has_iam_policy_with_lambda_invoke(synth_template):
    """IAM policy must include lambda:InvokeFunction."""
    template_json = synth_template.to_json()
    found = False
    for resource in template_json.get("Resources", {}).values():
        if resource.get("Type") == "AWS::IAM::Policy":
            doc = resource["Properties"].get("PolicyDocument", {})
            for statement in doc.get("Statement", []):
                actions = statement.get("Action")
                if isinstance(actions, str):
                    actions = [actions]
                if actions and "lambda:InvokeFunction" in actions:
                    found = True
    assert found, "No IAM policy found with lambda:InvokeFunction"


def test_has_iam_policy_with_bedrock_invoke(synth_template):
    """IAM policy must include bedrock:InvokeModel."""
    template_json = synth_template.to_json()
    found = False
    for resource in template_json.get("Resources", {}).values():
        if resource.get("Type") == "AWS::IAM::Policy":
            doc = resource["Properties"].get("PolicyDocument", {})
            for statement in doc.get("Statement", []):
                actions = statement.get("Action")
                if isinstance(actions, str):
                    actions = [actions]
                if actions and "bedrock:InvokeModel" in actions:
                    found = True
    assert found, "No IAM policy found with bedrock:InvokeModel"


def test_no_wildcard_lambda_actions(synth_template):
    """Lambda IAM must not use wildcard actions."""
    template_json = synth_template.to_json()
    for resource in template_json.get("Resources", {}).values():
        if resource.get("Type") == "AWS::IAM::Policy":
            doc = resource["Properties"].get("PolicyDocument", {})
            for statement in doc.get("Statement", []):
                actions = statement.get("Action")
                if isinstance(actions, str):
                    actions = [actions]
                if actions and "lambda:InvokeFunction" in actions:
                    assert "*" not in actions, "Lambda IAM must not use wildcard actions"


def test_runtime_has_environment_variables(synth_template):
    """Runtime must have TOOLS_LAMBDA_ARN environment variable configured."""
    template_json = synth_template.to_json()
    for resource in template_json.get("Resources", {}).values():
        if resource.get("Type") == "AWS::BedrockAgentCore::Runtime":
            props = resource.get("Properties", {})
            env_vars = props.get("EnvironmentVariables", {})
            assert "TOOLS_LAMBDA_ARN" in env_vars, \
                "Runtime must have TOOLS_LAMBDA_ARN environment variable"
            return
    pytest.fail("No AWS::BedrockAgentCore::Runtime resource found")
