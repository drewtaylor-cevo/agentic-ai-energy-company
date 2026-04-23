#!/usr/bin/env python3
"""CDK entry point for Customer Tariff demo.

Region is hardcoded to us-east-1 because the local AWS profile defaults to
ap-southeast-2 and AgentCore Agent Registry (required in Phase 2+) is NOT
available in ap-southeast-2. Never rely on environment default.
"""
import aws_cdk as cdk

app = cdk.App()

# FoundationStack wiring is added in Plan 03 (03-01-PLAN). Until then this app
# synthesizes to an empty cloud assembly so scaffolding can be verified.
# from infrastructure.foundation_stack import FoundationStack
# FoundationStack(app, "CustomerTariff",
#     env=cdk.Environment(region="us-east-1"),
#     description="Phase 1: Foundation + Dummy Data")

app.synth()
