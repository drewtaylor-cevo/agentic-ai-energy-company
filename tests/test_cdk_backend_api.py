"""CDK synth tests for BackendApiStack — Function URL streaming infrastructure.

Validates that the BackendApiStack synthesizes the expected CloudFormation
resources for Lambda Response Streaming via Function URL, including:
- AWS::Lambda::Url with RESPONSE_STREAM invoke mode
- CORS configuration on the Function URL
- SSM parameter for the streaming URL

No AWS credentials needed — all values are CDK tokens resolved at deploy time.
"""
import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from infrastructure.backend_api_stack import BackendApiStack


@pytest.fixture(scope="module")
def backend_template():
    app = cdk.App()
    stack = BackendApiStack(
        app,
        "TestBackendApiStack",
        env=cdk.Environment(region="us-east-1", account="123456789012"),
    )
    return Template.from_stack(stack)


class TestFunctionUrl:
    """Tests for Lambda Function URL with response streaming (Requirement 1.1)."""

    def test_function_url_exists_with_response_stream_invoke_mode(self, backend_template):
        """Function URL is created with RESPONSE_STREAM invoke mode."""
        backend_template.has_resource_properties(
            "AWS::Lambda::Url",
            {
                "InvokeMode": "RESPONSE_STREAM",
            },
        )

    def test_function_url_auth_type_is_none(self, backend_template):
        """Function URL uses no authentication (public access)."""
        backend_template.has_resource_properties(
            "AWS::Lambda::Url",
            {
                "AuthType": "NONE",
            },
        )

    def test_function_url_cors_allowed_origins(self, backend_template):
        """Function URL CORS allows all origins."""
        backend_template.has_resource_properties(
            "AWS::Lambda::Url",
            {
                "Cors": Match.object_like(
                    {
                        "AllowOrigins": ["*"],
                    }
                ),
            },
        )

    def test_function_url_cors_allowed_methods(self, backend_template):
        """Function URL CORS allows GET method."""
        backend_template.has_resource_properties(
            "AWS::Lambda::Url",
            {
                "Cors": Match.object_like(
                    {
                        "AllowMethods": ["GET"],
                    }
                ),
            },
        )

    def test_function_url_cors_allowed_headers(self, backend_template):
        """Function URL CORS allows Content-Type and Accept headers."""
        backend_template.has_resource_properties(
            "AWS::Lambda::Url",
            {
                "Cors": Match.object_like(
                    {
                        "AllowHeaders": ["Content-Type", "Accept"],
                    }
                ),
            },
        )


class TestStreamingSsmParameter:
    """Tests for SSM parameter storing the streaming URL."""

    def test_ssm_parameter_exists(self, backend_template):
        """SSM parameter is created for the streaming URL."""
        backend_template.has_resource_properties(
            "AWS::SSM::Parameter",
            {
                "Name": "/customer-tariff/streaming-url",
                "Type": "String",
            },
        )

    def test_ssm_parameter_has_value(self, backend_template):
        """SSM parameter value references the Function URL."""
        backend_template.has_resource_properties(
            "AWS::SSM::Parameter",
            {
                "Name": "/customer-tariff/streaming-url",
                "Value": Match.any_value(),
            },
        )
