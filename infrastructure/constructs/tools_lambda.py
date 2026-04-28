"""Lambda function construct — bundles the lambda/ directory as an asset.

Runtime is Python 3.12. The entire lambda/ directory (handler.py +
tariff_plans.json) is zipped via Code.from_asset. table.grant_read_data
gives scoped IAM permissions (dynamodb:GetItem, Query, Scan) on this table
only — no wildcards.
"""
from aws_cdk import Duration
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class ToolsLambdaConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.Table,
    ) -> None:
        super().__init__(scope, construct_id)

        self.function = lambda_.Function(
            self,
            "TariffTools",
            function_name="tariff-tools",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("lambda"),
            environment={"TABLE_NAME": table.table_name},
            timeout=Duration.seconds(10),
            memory_size=256,
        )

        table.grant_read_data(self.function)
