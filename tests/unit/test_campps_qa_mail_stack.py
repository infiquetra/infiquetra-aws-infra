"""Unit tests for the team-hermod QA inbound mail stack."""

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.campps_qa_mail_stack import (
    QA_MAIL_BUCKET_NAME,
    QA_MAIL_DOMAIN,
    CamppsQaMailStack,
)


def synth_template() -> Template:
    app = App()
    stack = CamppsQaMailStack(
        app,
        "TestCamppsQaMailStack",
        env=Environment(account="477152411873", region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_bucket_is_encrypted_private_and_expires_after_7_days() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketName": QA_MAIL_BUCKET_NAME,
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            },
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
            "LifecycleConfiguration": {
                "Rules": Match.array_with(
                    [Match.object_like({"ExpirationInDays": 7, "Status": "Enabled"})]
                )
            },
        },
    )


def test_bucket_policy_is_tls_only_and_ses_scoped_to_account() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Effect": "Deny",
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            }
                        ),
                        Match.object_like(
                            {
                                "Sid": "AllowSESPutsFromThisAccount",
                                "Principal": {"Service": "ses.amazonaws.com"},
                                "Action": "s3:PutObject",
                                "Condition": {
                                    "StringEquals": Match.object_like(
                                        {"AWS:SourceAccount": "477152411873"}
                                    )
                                },
                            }
                        ),
                    ]
                )
            }
        },
    )


def test_domain_identity_and_catch_all_receipt_rule_store_to_s3() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SES::EmailIdentity", {"EmailIdentity": QA_MAIL_DOMAIN}
    )
    template.resource_count_is("AWS::SES::ReceiptRuleSet", 1)
    template.has_resource_properties(
        "AWS::SES::ReceiptRule",
        {
            "Rule": Match.object_like(
                {
                    "Enabled": True,
                    "Recipients": [QA_MAIL_DOMAIN],
                    "Actions": [
                        {"S3Action": Match.object_like({"ObjectKeyPrefix": "inbound/"})}
                    ],
                }
            )
        },
    )
