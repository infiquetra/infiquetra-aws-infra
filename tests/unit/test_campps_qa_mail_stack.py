"""Unit tests for the team-hermod QA inbound mail stack."""

import json

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


def test_reader_function_url_requires_iam_auth() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"FunctionName": "campps-qa-mail-reader", "Runtime": "python3.13"},
    )
    template.resource_count_is("AWS::Lambda::Url", 1)
    template.has_resource_properties("AWS::Lambda::Url", {"AuthType": "AWS_IAM"})


def test_reader_role_reads_only_inbound_of_qa_bucket() -> None:
    template_json = synth_template().to_json()
    policies = [
        r["Properties"]["PolicyDocument"]["Statement"]
        for r in template_json["Resources"].values()
        if r["Type"] == "AWS::IAM::Policy"
    ]
    statements = [s for doc in policies for s in doc]
    s3_statements = [
        s
        for s in statements
        if any(str(a).startswith("s3:") for a in _as_list(s["Action"]))
    ]
    assert {s.get("Sid") for s in s3_statements} == {
        "ListInboundOnly",
        "ReadAndTagInboundObjects",
    }
    for s in s3_statements:
        assert s["Effect"] == "Allow"
        assert "s3:DeleteObject" not in _as_list(s["Action"])
        assert "s3:PutObject" not in _as_list(s["Action"])
    listing = next(s for s in s3_statements if s["Sid"] == "ListInboundOnly")
    assert listing["Condition"] == {"StringLike": {"s3:prefix": ["inbound/*"]}}
    objects = next(s for s in s3_statements if s["Sid"] == "ReadAndTagInboundObjects")
    resource = json.dumps(objects["Resource"])
    assert "/inbound/*" in resource


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else [value]
