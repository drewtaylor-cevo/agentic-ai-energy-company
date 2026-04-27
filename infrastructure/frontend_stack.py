"""Phase 4 CDK stack — Amplify Hosting for the demo UI.

Fully independent stack with no cross-stack dependencies. Deploys the
pre-built ui/dist directory to Amplify Hosting via an S3 asset.
"""
from aws_cdk import CfnOutput, Stack
from constructs import Construct

from infrastructure.constructs.amplify_hosting import AmplifyHostingConstruct


class FrontendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        hosting = AmplifyHostingConstruct(self, "AmplifyHosting", asset_path="ui/dist")

        CfnOutput(self, "AmplifyAppUrl", value=hosting.app_url)
        CfnOutput(self, "AmplifyAppId", value=hosting.app_id)
