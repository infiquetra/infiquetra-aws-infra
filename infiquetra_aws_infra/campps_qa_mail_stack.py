"""SES inbound mail for team-hermod QA test inboxes (CAMPPS nonprod only)."""

from pathlib import Path
from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ses as ses
from aws_cdk import aws_ses_actions as ses_actions
from constructs import Construct

QA_MAIL_DOMAIN = "qa.infiquetra.com"
QA_MAIL_ACCOUNT_ID = "477152411873"  # campps-nonprod
QA_MAIL_REGION = "us-east-1"
QA_MAIL_BUCKET_NAME = f"infiquetra-campps-qa-mail-{QA_MAIL_ACCOUNT_ID}"
QA_MAIL_PREFIX = "inbound/"
QA_MAIL_RULE_SET_NAME = "campps-qa-inbound"
QA_MAIL_RULE_NAME = "qa-catch-all-to-s3"
QA_MAIL_RETENTION_DAYS = 7
QA_MAIL_READER_FUNCTION_NAME = "campps-qa-mail-reader"
QA_MAIL_READER_SRC = Path(__file__).parent / "lambda_src" / "qa_mail_reader"
SES_INBOUND_MX = f"inbound-smtp.{QA_MAIL_REGION}.amazonaws.com"


class CamppsQaMailStack(Stack):
    """Catch-all SES receiving for qa.infiquetra.com, stored in a 7-day S3 bucket."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "QaMailBucket",
            bucket_name=QA_MAIL_BUCKET_NAME,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ExpireQaMail",
                    enabled=True,
                    expiration=Duration.days(QA_MAIL_RETENTION_DAYS),
                    abort_incomplete_multipart_upload_after=Duration.days(1),
                )
            ],
        )

        rule_arn = (
            f"arn:{self.partition}:ses:{self.region}:{self.account}:"
            f"receipt-rule-set/{QA_MAIL_RULE_SET_NAME}:receipt-rule/{QA_MAIL_RULE_NAME}"
        )
        bucket_policy = bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowSESPutsFromThisAccount",
                principals=[iam.ServicePrincipal("ses.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[bucket.arn_for_objects(f"{QA_MAIL_PREFIX}*")],
                conditions={
                    "StringEquals": {
                        "AWS:SourceAccount": self.account,
                        "AWS:SourceArn": rule_arn,
                    }
                },
            )
        )

        identity = ses.EmailIdentity(
            self,
            "QaMailDomainIdentity",
            identity=ses.Identity.domain(QA_MAIL_DOMAIN),
        )

        rule_set = ses.ReceiptRuleSet(
            self,
            "QaMailRuleSet",
            receipt_rule_set_name=QA_MAIL_RULE_SET_NAME,
        )
        rule = rule_set.add_rule(
            "QaCatchAllToS3",
            receipt_rule_name=QA_MAIL_RULE_NAME,
            recipients=[QA_MAIL_DOMAIN],
            enabled=True,
            scan_enabled=True,
            tls_policy=ses.TlsPolicy.OPTIONAL,
            actions=[
                ses_actions.S3(bucket=bucket, object_key_prefix=QA_MAIL_PREFIX),
            ],
        )
        # SES validates bucket write access when the rule is created.
        if bucket_policy.policy_dependable is not None:
            rule.node.add_dependency(bucket_policy.policy_dependable)

        self.reader = self._create_reader(bucket)

        CfnOutput(self, "QaMailBucketName", value=bucket.bucket_name)
        CfnOutput(self, "QaMailRuleSetName", value=QA_MAIL_RULE_SET_NAME)
        CfnOutput(
            self, "QaMailMxRecord", value=f"{QA_MAIL_DOMAIN} MX 10 {SES_INBOUND_MX}"
        )
        for index, record in enumerate(identity.dkim_records, start=1):
            CfnOutput(
                self,
                f"QaMailDkimCname{index}",
                value=f"{record.name} CNAME {record.value}",
            )

    def _create_reader(self, bucket: s3.Bucket) -> lambda_.Function:
        """Read-only lookup behind an AWS_IAM function URL (inbound/ only)."""

        role = iam.Role(
            self,
            "QaMailReaderRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="QA mail reader: read inbound/ in the QA mail bucket only",
        )
        role.add_to_policy(
            iam.PolicyStatement(
                sid="ListInboundOnly",
                actions=["s3:ListBucket"],
                resources=[bucket.bucket_arn],
                conditions={"StringLike": {"s3:prefix": [f"{QA_MAIL_PREFIX}*"]}},
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                sid="ReadAndTagInboundObjects",
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                ],
                resources=[bucket.arn_for_objects(f"{QA_MAIL_PREFIX}*")],
            )
        )

        log_group = logs.LogGroup(
            self,
            "QaMailReaderLogs",
            log_group_name=f"/aws/lambda/{QA_MAIL_READER_FUNCTION_NAME}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[log_group.log_group_arn],
            )
        )

        reader = lambda_.Function(
            self,
            "QaMailReader",
            function_name=QA_MAIL_READER_FUNCTION_NAME,
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(QA_MAIL_READER_SRC)),
            role=role,
            timeout=Duration.seconds(30),
            memory_size=256,
            log_group=log_group,
            environment={"QA_MAIL_BUCKET": bucket.bucket_name},
        )
        url = reader.add_function_url(auth_type=lambda_.FunctionUrlAuthType.AWS_IAM)
        CfnOutput(self, "QaMailReaderUrl", value=url.url)
        CfnOutput(self, "QaMailReaderFunctionName", value=reader.function_name)
        return reader
