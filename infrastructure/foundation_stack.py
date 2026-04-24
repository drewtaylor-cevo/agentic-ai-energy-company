"""Phase 1 CDK stack — wires billing table, tools lambda, and seeder.

Stack-level wiring only: no resource definitions inline. All resource logic
lives in the construct classes under infrastructure/constructs/.
"""
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from infrastructure.constructs.billing_table import BillingTableConstruct
from infrastructure.constructs.seeder import SeederConstruct
from infrastructure.constructs.tools_lambda import ToolsLambdaConstruct


class FoundationStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        billing = BillingTableConstruct(self, "BillingTable")
        tools = ToolsLambdaConstruct(self, "ToolsLambda", table=billing.table)
        seeder = SeederConstruct(self, "Seeder", table=billing.table)

        # Outputs let the user grab ARNs/names after cdk deploy.
        CfnOutput(self, "BillingTableName", value=billing.table.table_name)
        CfnOutput(self, "BillingTableArn", value=billing.table.table_arn)
        CfnOutput(self, "ToolsLambdaName", value=tools.function.function_name)
        CfnOutput(self, "ToolsLambdaArn", value=tools.function.function_arn)

        # Cross-stack wiring: write ToolsLambda ARN to SSM so AgentCoreStack
        # can read it without a hard CloudFormation export dependency (Pitfall 5).
        ssm.StringParameter(
            self,
            "ToolsLambdaArnParam",
            parameter_name="/customer-tariff/tools-lambda-arn",
            string_value=tools.function.function_arn,
            description="ToolsLambda ARN for AgentCoreStack cross-stack wiring",
        )
