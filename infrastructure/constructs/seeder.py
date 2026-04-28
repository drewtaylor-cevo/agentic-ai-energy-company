"""DynamoDB seeder construct — one-shot population via AwsCustomResource.

Creates N AwsCustomResource instances, each backed by a CDK-auto-generated
Lambda that calls DynamoDB.batchWriteItem. BatchWriteItem accepts a maximum
of 25 items per call, so 73 records require 3 batches (25 + 25 + 23).

Uses on_create ONLY — on_update would re-run seeding on every cdk deploy,
overwriting any manually modified records. To force re-seed, change the
physical_resource_id string suffix (vN → vN+1).

Resource-id version history:
  v1 — original demo-v2.0 release (36 items: CUST-001/002/003)
  v2 — Phase 11 re-chunk (73 items: +CUST-004/005/006 + PROFILE row).
       Bumped because seed growth 36→73 shifted batch contents — Seeder1
       now carries CUST-003 tail + new CUST-004/005 rows, and without a
       phys-id bump CFN treats it as a no-op update (v1 on_create already
       fired, no on_update handler defined). BatchWriteItem is a PutItem
       under the hood, so re-running on existing CUST-001/002/003 rows is
       byte-exact-idempotent — the preserved records in DYNAMO_RECORDS are
       byte-identical to what v1 wrote.

IAM is scoped to dynamodb:BatchWriteItem on this table ARN only.
"""
import math
from typing import List

from aws_cdk import custom_resources as cr
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from constructs import Construct

from infrastructure.seed_data.billing_records import DYNAMO_RECORDS

_BATCH_SIZE = 25


class SeederConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        table: dynamodb.Table,
    ) -> None:
        super().__init__(scope, construct_id)

        records: List[dict] = DYNAMO_RECORDS
        num_batches = math.ceil(len(records) / _BATCH_SIZE)

        self.seeders = []
        for i in range(num_batches):
            batch = records[i * _BATCH_SIZE : (i + 1) * _BATCH_SIZE]
            request_items = [{"PutRequest": {"Item": record}} for record in batch]

            seeder = cr.AwsCustomResource(
                self,
                f"BillingSeeder{i}",
                on_create=cr.AwsSdkCall(
                    service="DynamoDB",
                    action="batchWriteItem",
                    parameters={
                        "RequestItems": {table.table_name: request_items}
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(
                        f"BillingSeeder-{i}-v2"
                    ),
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:BatchWriteItem"],
                        resources=[table.table_arn],
                    ),
                ]),
            )
            seeder.node.add_dependency(table)
            self.seeders.append(seeder)
