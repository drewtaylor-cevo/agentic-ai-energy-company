"""DynamoDB billing table construct.

Single-table design: customer_id (PK) + month (SK).
Only access pattern is PK = CUST-XXX returning 12 items sorted by SK,
so no GSI is needed. PAY_PER_REQUEST avoids capacity planning; DESTROY
removal policy ensures cdk destroy cleans up without orphaned tables.
"""
from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class BillingTableConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(
            self,
            "TariffBillingTable",
            table_name="tariff-billing",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="month",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=False,
        )
