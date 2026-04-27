#!/usr/bin/env python3
"""CDK entry point for Customer Tariff demo.

Region is hardcoded to us-east-1 because the local AWS profile defaults to
ap-southeast-2 and AgentCore Agent Registry (required in Phase 2+) is NOT
available in ap-southeast-2. Never rely on environment default.
"""
import aws_cdk as cdk

from infrastructure.agentcore_stack import AgentCoreStack
from infrastructure.backend_api_stack import BackendApiStack
from infrastructure.foundation_stack import FoundationStack
from infrastructure.frontend_stack import FrontendStack

app = cdk.App()

FoundationStack(
    app,
    "CustomerTariff",
    env=cdk.Environment(region="us-east-1"),
    description="Phase 1: Foundation + Dummy Data",
)

AgentCoreStack(
    app,
    "CustomerTariffAgent",
    env=cdk.Environment(region="us-east-1"),
    description="Phase 2: AgentCore Agent Runtime",
)

BackendApiStack(
    app,
    "CustomerTariffApi",
    env=cdk.Environment(region="us-east-1"),
    description="Phase 3: Backend API",
)

FrontendStack(
    app,
    "CustomerTariffFrontend",
    env=cdk.Environment(region="us-east-1"),
    description="Amplify Hosting for the demo UI",
)

app.synth()
