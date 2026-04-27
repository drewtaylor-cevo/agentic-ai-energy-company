"""Amplify Hosting construct — deploys a pre-built static site to Amplify.

Packages a local dist directory (e.g. ui/dist) as an S3 asset and deploys it
to an Amplify Hosting app with platform=WEB (static-only, no SSR).  Configures
the SPA redirect rule so client-side routing and query params (?narrative=off)
work correctly, and adds security response headers on all paths.

The construct exposes app_url and app_id properties for CfnOutput wiring in
the parent stack.
"""

import aws_cdk.aws_amplify_alpha as amplify
from aws_cdk import aws_s3_assets as assets
from constructs import Construct


class AmplifyHostingConstruct(Construct):
    """Amplify Hosting app deployed from a pre-built static asset."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        asset_path: str,
    ) -> None:
        super().__init__(scope, construct_id)

        # Package the pre-built dist directory as an S3 asset.
        asset = assets.Asset(self, "FrontendAsset", path=asset_path)

        # Amplify App — static-only (platform=WEB), no source code provider.
        self._app = amplify.App(
            self,
            "AmplifyApp",
            app_name="customer-tariff-ui",
            platform=amplify.Platform.WEB,
            custom_rules=[amplify.CustomRule.SINGLE_PAGE_APPLICATION_REDIRECT],
            custom_response_headers=[
                amplify.CustomResponseHeader(
                    pattern="**/*",
                    headers={
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "Referrer-Policy": "strict-origin-when-cross-origin",
                    },
                )
            ],
        )

        # Single branch deployed from the S3 asset.
        self._branch = self._app.add_branch("main", asset=asset)

        # Construct the default Amplify URL.
        self._app_url = f"https://main.{self._app.app_id}.amplifyapp.com"

    @property
    def app_url(self) -> str:
        """The default Amplify app URL (https://main.<app-id>.amplifyapp.com)."""
        return self._app_url

    @property
    def app_id(self) -> str:
        """The Amplify app ID."""
        return self._app.app_id
