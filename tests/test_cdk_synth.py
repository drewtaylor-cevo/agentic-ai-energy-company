"""Offline CDK synth test — no AWS credentials needed.

Synthesizes the FoundationStack in-memory and inspects the CloudFormation
template for expected resources, types, and properties. Any drift from the
RESEARCH.md architecture will be caught here before cdk deploy.
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infrastructure.foundation_stack import FoundationStack


@pytest.fixture(scope="module")
def synth_template():
    app = cdk.App()
    stack = FoundationStack(
        app,
        "TestStack",
        env=cdk.Environment(region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_has_one_dynamodb_table(synth_template):
    synth_template.resource_count_is("AWS::DynamoDB::Table", 1)


def test_table_has_composite_key(synth_template):
    synth_template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "KeySchema": [
                {"AttributeName": "customer_id", "KeyType": "HASH"},
                {"AttributeName": "month", "KeyType": "RANGE"},
            ],
        },
    )


def test_table_billing_mode_is_on_demand(synth_template):
    synth_template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {"BillingMode": "PAY_PER_REQUEST"},
    )


def test_table_removal_policy_is_destroy(synth_template):
    # DESTROY translates to DeletionPolicy "Delete" in CloudFormation JSON.
    synth_template.has_resource(
        "AWS::DynamoDB::Table",
        {"DeletionPolicy": "Delete", "UpdateReplacePolicy": "Delete"},
    )


def test_has_tools_lambda(synth_template):
    synth_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Runtime": "python3.12",
            "Handler": "handler.simulate_savings",
            "FunctionName": "tariff-tools",
        },
    )


def test_lambda_has_table_name_env(synth_template):
    # Environment.Variables.TABLE_NAME should reference the table name via Ref.
    synth_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "tariff-tools",
            "Environment": {
                "Variables": {"TABLE_NAME": Match.any_value()},
            },
        },
    )


def test_seeder_creates_two_batches(synth_template):
    # Each AwsCustomResource renders as one Custom::AWS CloudFormation resource.
    # With 36 records at 25/batch we expect exactly 2 seeder resources.
    synth_template.resource_count_is("Custom::AWS", 2)


def test_seeder_iam_scoped_to_batchwriteitem(synth_template):
    # At least one IAM policy document in the template must contain
    # dynamodb:BatchWriteItem as a scoped action (not a wildcard).
    template_json = synth_template.to_json()
    found = False
    for resource in template_json.get("Resources", {}).values():
        if resource.get("Type") == "AWS::IAM::Policy":
            doc = resource["Properties"].get("PolicyDocument", {})
            for statement in doc.get("Statement", []):
                actions = statement.get("Action")
                if isinstance(actions, str):
                    actions = [actions]
                if actions and "dynamodb:BatchWriteItem" in actions:
                    assert "*" not in actions, "seeder IAM must not use wildcard actions"
                    found = True
    assert found, "No IAM policy found with dynamodb:BatchWriteItem"
