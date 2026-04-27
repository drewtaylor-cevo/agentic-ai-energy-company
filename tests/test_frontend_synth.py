"""Offline CDK synth tests for the FrontendStack (Amplify Hosting).

Synthesizes the FrontendStack in-memory using a temporary ui/dist directory
and inspects the CloudFormation template for expected Amplify resources,
properties, and outputs.

Requirements: 1.1, 1.2, 1.4, 6.2
"""
import os
import tempfile

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from infrastructure.frontend_stack import FrontendStack


@pytest.fixture(scope="module")
def frontend_stack_and_template():
    """Synthesize FrontendStack with a temporary ui/dist directory.

    FrontendStack hardcodes asset_path="ui/dist", so we create a temp
    workspace with that structure and chdir into it for synthesis.

    Returns a (stack, template) tuple so tests can inspect both the CDK
    stack object and the synthesized CloudFormation template.
    """
    original_cwd = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    try:
        # Build the expected ui/dist structure with dummy content.
        dist_dir = os.path.join(tmpdir, "ui", "dist")
        assets_dir = os.path.join(dist_dir, "assets")
        os.makedirs(assets_dir)
        with open(os.path.join(dist_dir, "index.html"), "w") as f:
            f.write("<html><body><div id='root'></div></body></html>\n")
        with open(os.path.join(assets_dir, "index-abc123.js"), "w") as f:
            f.write("// dummy bundle\n")

        os.chdir(tmpdir)

        app = cdk.App()
        stack = FrontendStack(
            app,
            "TestFrontend",
            env=cdk.Environment(region="us-east-1"),
        )
        template = Template.from_stack(stack)
        return stack, template
    finally:
        os.chdir(original_cwd)


@pytest.fixture(scope="module")
def synth_template(frontend_stack_and_template):
    """The synthesized CloudFormation Template for the FrontendStack."""
    return frontend_stack_and_template[1]


@pytest.fixture(scope="module")
def frontend_stack(frontend_stack_and_template):
    """The FrontendStack CDK stack object."""
    return frontend_stack_and_template[0]


def test_has_one_amplify_app(synth_template):
    synth_template.resource_count_is("AWS::Amplify::App", 1)


def test_has_one_amplify_branch(synth_template):
    synth_template.resource_count_is("AWS::Amplify::Branch", 1)


def test_amplify_app_name(synth_template):
    synth_template.has_resource_properties(
        "AWS::Amplify::App",
        {"Name": "customer-tariff-ui"},
    )


def test_amplify_platform_is_web(synth_template):
    synth_template.has_resource_properties(
        "AWS::Amplify::App",
        {"Platform": "WEB"},
    )


def test_has_amplify_app_url_output(synth_template):
    outputs = synth_template.to_json().get("Outputs", {})
    assert any(
        "AmplifyAppUrl" in key for key in outputs
    ), "Expected AmplifyAppUrl CfnOutput"


def test_has_amplify_app_id_output(synth_template):
    outputs = synth_template.to_json().get("Outputs", {})
    assert any(
        "AmplifyAppId" in key for key in outputs
    ), "Expected AmplifyAppId CfnOutput"


# ---------------------------------------------------------------------------
# Property 2: Stack independence (no cross-stack references)
# Validates: Requirements 1.3, 5.1, 5.2, 9.2
# ---------------------------------------------------------------------------

import json
import yaml


class TestStackIndependence:
    """**Validates: Requirements 1.3, 5.1, 5.2, 9.2**

    Property 2: Stack independence — the FrontendStack must have zero
    cross-stack references and no stack dependencies, ensuring it can be
    deployed, updated, or destroyed independently of the other stacks.
    """

    def test_no_fn_import_value_in_template(self, synth_template):
        """The synthesized template must contain zero Fn::ImportValue references."""
        template_json = synth_template.to_json()
        template_str = json.dumps(template_json)
        assert "Fn::ImportValue" not in template_str, (
            "Template contains Fn::ImportValue — the FrontendStack must not "
            "import values from other stacks"
        )

    def test_stack_has_no_dependencies(self, frontend_stack):
        """stack.dependencies must be an empty list (no cross-stack deps)."""
        assert frontend_stack.dependencies == [], (
            f"FrontendStack has unexpected dependencies: "
            f"{[d.stack_name for d in frontend_stack.dependencies]}"
        )


# ---------------------------------------------------------------------------
# Property 3: Security headers completeness
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ---------------------------------------------------------------------------


class TestSecurityHeadersCompleteness:
    """**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

    Property 3: Security headers completeness — the Amplify App resource
    must include custom response headers containing all three required
    security headers applied to the pattern ``**/*``.
    """

    REQUIRED_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    EXPECTED_PATTERN = "**/*"

    @pytest.fixture(scope="class")
    def custom_headers(self, synth_template):
        """Parse the CustomHeaders YAML string from the Amplify App resource."""
        template_json = synth_template.to_json()
        for resource in template_json.get("Resources", {}).values():
            if resource.get("Type") == "AWS::Amplify::App":
                raw = resource["Properties"]["CustomHeaders"]
                return yaml.safe_load(raw)
        pytest.fail("No AWS::Amplify::App resource found in template")

    def test_custom_headers_property_exists(self, synth_template):
        """The Amplify App resource must have a CustomHeaders property."""
        template_json = synth_template.to_json()
        for resource in template_json.get("Resources", {}).values():
            if resource.get("Type") == "AWS::Amplify::App":
                assert "CustomHeaders" in resource.get("Properties", {}), (
                    "Amplify App resource is missing the CustomHeaders property"
                )
                return
        pytest.fail("No AWS::Amplify::App resource found in template")

    def test_headers_applied_to_wildcard_pattern(self, custom_headers):
        """Headers must be applied to the pattern **/* (Requirement 3.1)."""
        patterns = [entry["pattern"] for entry in custom_headers["customHeaders"]]
        assert self.EXPECTED_PATTERN in patterns, (
            f"Expected pattern '{self.EXPECTED_PATTERN}' in custom headers, "
            f"got patterns: {patterns}"
        )

    def test_x_content_type_options_header(self, custom_headers):
        """X-Content-Type-Options must be set to nosniff (Requirement 3.2)."""
        self._assert_header_present(
            custom_headers, "X-Content-Type-Options", "nosniff"
        )

    def test_x_frame_options_header(self, custom_headers):
        """X-Frame-Options must be set to DENY (Requirement 3.3)."""
        self._assert_header_present(custom_headers, "X-Frame-Options", "DENY")

    def test_referrer_policy_header(self, custom_headers):
        """Referrer-Policy must be set to strict-origin-when-cross-origin (Requirement 3.4)."""
        self._assert_header_present(
            custom_headers, "Referrer-Policy", "strict-origin-when-cross-origin"
        )

    def test_all_three_security_headers_present(self, custom_headers):
        """All three required security headers must be present on the **/* pattern."""
        wildcard_entry = None
        for entry in custom_headers["customHeaders"]:
            if entry["pattern"] == self.EXPECTED_PATTERN:
                wildcard_entry = entry
                break

        assert wildcard_entry is not None, (
            f"No custom header entry found for pattern '{self.EXPECTED_PATTERN}'"
        )

        actual_headers = {
            h["key"]: h["value"] for h in wildcard_entry["headers"]
        }

        for key, value in self.REQUIRED_HEADERS.items():
            assert key in actual_headers, (
                f"Missing security header '{key}' in custom headers. "
                f"Found: {list(actual_headers.keys())}"
            )
            assert actual_headers[key] == value, (
                f"Security header '{key}' has value '{actual_headers[key]}', "
                f"expected '{value}'"
            )

    def _assert_header_present(self, custom_headers, key, expected_value):
        """Helper: assert a specific header key/value exists on the **/* pattern."""
        for entry in custom_headers["customHeaders"]:
            if entry["pattern"] == self.EXPECTED_PATTERN:
                for header in entry["headers"]:
                    if header["key"] == key:
                        assert header["value"] == expected_value, (
                            f"Header '{key}' has value '{header['value']}', "
                            f"expected '{expected_value}'"
                        )
                        return
                pytest.fail(
                    f"Header '{key}' not found in pattern '{self.EXPECTED_PATTERN}'"
                )
        pytest.fail(f"No custom header entry for pattern '{self.EXPECTED_PATTERN}'")


# ---------------------------------------------------------------------------
# Property 4: SPA redirect rule presence
# Validates: Requirements 2.1, 2.2, 2.3
# ---------------------------------------------------------------------------


class TestSpaRedirectRulePresence:
    """**Validates: Requirements 2.1, 2.2, 2.3**

    Property 4: SPA redirect rule presence — the Amplify App resource must
    include the SPA redirect custom rule that rewrites non-file paths to
    index.html with HTTP 200, enabling client-side routing and query
    parameter support (e.g. ?narrative=off).
    """

    # CDK's CustomRule.SINGLE_PAGE_APPLICATION_REDIRECT synthesizes to a
    # regex-based source pattern in CloudFormation rather than the literal
    # /<*> shorthand.  The regex </^[^.]+$/> matches URL paths that contain
    # no dots (i.e. not static files), rewriting them to /index.html.
    EXPECTED_SOURCE = "</^[^.]+$/>"
    EXPECTED_TARGET = "/index.html"
    EXPECTED_STATUS = "200"

    @pytest.fixture(scope="class")
    def custom_rules(self, synth_template):
        """Extract the CustomRules list from the Amplify App resource."""
        template_json = synth_template.to_json()
        for resource in template_json.get("Resources", {}).values():
            if resource.get("Type") == "AWS::Amplify::App":
                rules = resource.get("Properties", {}).get("CustomRules", [])
                return rules
        pytest.fail("No AWS::Amplify::App resource found in template")

    def test_custom_rules_property_exists(self, synth_template):
        """The Amplify App resource must have a CustomRules property."""
        template_json = synth_template.to_json()
        for resource in template_json.get("Resources", {}).values():
            if resource.get("Type") == "AWS::Amplify::App":
                assert "CustomRules" in resource.get("Properties", {}), (
                    "Amplify App resource is missing the CustomRules property"
                )
                return
        pytest.fail("No AWS::Amplify::App resource found in template")

    def test_spa_redirect_rule_source(self, custom_rules):
        """SPA redirect rule must have the regex source pattern (Requirement 2.1)."""
        sources = [r.get("Source") for r in custom_rules]
        assert self.EXPECTED_SOURCE in sources, (
            f"Expected SPA redirect source '{self.EXPECTED_SOURCE}' in "
            f"CustomRules, got sources: {sources}"
        )

    def test_spa_redirect_rule_target(self, custom_rules):
        """SPA redirect rule must have target /index.html (Requirement 2.2)."""
        for rule in custom_rules:
            if rule.get("Source") == self.EXPECTED_SOURCE:
                assert rule.get("Target") == self.EXPECTED_TARGET, (
                    f"SPA redirect rule target is '{rule.get('Target')}', "
                    f"expected '{self.EXPECTED_TARGET}'"
                )
                return
        pytest.fail(
            f"No custom rule with source '{self.EXPECTED_SOURCE}' found"
        )

    def test_spa_redirect_rule_status(self, custom_rules):
        """SPA redirect rule must have status 200 (Requirement 2.3)."""
        for rule in custom_rules:
            if rule.get("Source") == self.EXPECTED_SOURCE:
                assert rule.get("Status") == self.EXPECTED_STATUS, (
                    f"SPA redirect rule status is '{rule.get('Status')}', "
                    f"expected '{self.EXPECTED_STATUS}'"
                )
                return
        pytest.fail(
            f"No custom rule with source '{self.EXPECTED_SOURCE}' found"
        )

    def test_spa_redirect_rule_complete(self, custom_rules):
        """The complete SPA redirect rule (source, target, status) must be present."""
        expected_rule = {
            "Source": self.EXPECTED_SOURCE,
            "Target": self.EXPECTED_TARGET,
            "Status": self.EXPECTED_STATUS,
        }
        matching = [
            r for r in custom_rules
            if (
                r.get("Source") == self.EXPECTED_SOURCE
                and r.get("Target") == self.EXPECTED_TARGET
                and r.get("Status") == self.EXPECTED_STATUS
            )
        ]
        assert len(matching) == 1, (
            f"Expected exactly one SPA redirect rule matching {expected_rule}, "
            f"found {len(matching)} in CustomRules: {custom_rules}"
        )


# ---------------------------------------------------------------------------
# Property 5: Static platform configuration
# Validates: Requirements 1.1, 6.1
# ---------------------------------------------------------------------------


class TestStaticPlatformConfiguration:
    """**Validates: Requirements 1.1, 6.1**

    Property 5: Static platform configuration — the Amplify App resource
    SHALL have Platform set to WEB (static-only, no SSR compute), ensuring
    HTTPS-only delivery via CloudFront CDN. The value must be exactly ``WEB``
    and not ``WEB_COMPUTE`` or any other variant.
    """

    EXPECTED_PLATFORM = "WEB"

    def test_amplify_app_has_platform_property(self, synth_template):
        """The Amplify App resource must have a Platform property defined."""
        template_json = synth_template.to_json()
        for resource in template_json.get("Resources", {}).values():
            if resource.get("Type") == "AWS::Amplify::App":
                assert "Platform" in resource.get("Properties", {}), (
                    "Amplify App resource is missing the Platform property"
                )
                return
        pytest.fail("No AWS::Amplify::App resource found in template")

    def test_platform_is_exactly_web(self, synth_template):
        """Platform must be exactly 'WEB', not 'WEB_COMPUTE' or any other value."""
        template_json = synth_template.to_json()
        for resource in template_json.get("Resources", {}).values():
            if resource.get("Type") == "AWS::Amplify::App":
                platform = resource["Properties"]["Platform"]
                assert platform == self.EXPECTED_PLATFORM, (
                    f"Amplify App Platform is '{platform}', "
                    f"expected exactly '{self.EXPECTED_PLATFORM}'"
                )
                return
        pytest.fail("No AWS::Amplify::App resource found in template")

    def test_platform_is_not_web_compute(self, synth_template):
        """Platform must not be WEB_COMPUTE (SSR mode)."""
        template_json = synth_template.to_json()
        for resource in template_json.get("Resources", {}).values():
            if resource.get("Type") == "AWS::Amplify::App":
                platform = resource["Properties"]["Platform"]
                assert platform != "WEB_COMPUTE", (
                    "Amplify App Platform is 'WEB_COMPUTE' (SSR mode) — "
                    "it must be 'WEB' for static-only hosting"
                )
                return
        pytest.fail("No AWS::Amplify::App resource found in template")

    def test_platform_value_via_template_assertion(self, synth_template):
        """Use CDK Template.has_resource_properties to formally assert Platform=WEB."""
        synth_template.has_resource_properties(
            "AWS::Amplify::App",
            {"Platform": self.EXPECTED_PLATFORM},
        )
