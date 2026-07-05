"""Unit tests for home-lab Route 53 DDNS IAM."""

from typing import Any

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.home_lab_dns_stack import HomeLabDnsStack

RECORD_NAMES_CONDITION_KEY = "route53:ChangeResourceRecordSetsNormalizedRecordNames"


def synth_template() -> Template:
    app = App()
    stack = HomeLabDnsStack(
        app,
        "TestHomeLabDnsStack",
        env=Environment(account="645166163764", region="us-east-1"),
    )
    return Template.from_stack(stack)


def policy_documents(template: Template) -> list[dict[str, Any]]:
    policies = template.find_resources("AWS::IAM::Policy")
    return [policy["Properties"]["PolicyDocument"] for policy in policies.values()]


def normalize_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def test_ddns_stack_creates_user_without_access_key() -> None:
    template = synth_template()

    template.has_parameter(
        "PublicHostedZoneId",
        {
            "Type": "String",
            "Description": Match.string_like_regexp(
                "Hosted zone ID for infiquetra.com"
            ),
        },
    )
    template.has_resource_properties(
        "AWS::IAM::User",
        {"UserName": "home-lab-route53-ddns"},
    )
    template.resource_count_is("AWS::IAM::AccessKey", 0)


def test_ddns_policy_limits_record_changes_to_allowed_a_record_upserts() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyName": "home-lab-route53-ddns",
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": "route53:ChangeResourceRecordSets",
                                "Resource": {
                                    "Fn::Join": Match.array_with(
                                        [
                                            "",
                                            Match.array_with(
                                                [
                                                    "arn:",
                                                    {"Ref": "AWS::Partition"},
                                                    ":route53:::hostedzone/",
                                                    {"Ref": "PublicHostedZoneId"},
                                                ]
                                            ),
                                        ]
                                    )
                                },
                                "Condition": {
                                    "ForAllValues:StringEquals": {
                                        "route53:ChangeResourceRecordSetsActions": [
                                            "UPSERT"
                                        ],
                                        "route53:ChangeResourceRecordSetsRecordTypes": [
                                            "A"
                                        ],
                                        RECORD_NAMES_CONDITION_KEY: [
                                            "webhooks.infiquetra.com"
                                        ],
                                    }
                                },
                            }
                        ),
                        Match.object_like(
                            {
                                "Action": "route53:ChangeResourceRecordSets",
                                "Resource": {
                                    "Fn::Join": Match.array_with(
                                        [
                                            "",
                                            Match.array_with(
                                                [
                                                    "arn:",
                                                    {"Ref": "AWS::Partition"},
                                                    ":route53:::hostedzone/Z0074496WS5CEFE97RIR",
                                                ]
                                            ),
                                        ]
                                    )
                                },
                                "Condition": {
                                    "ForAllValues:StringEquals": {
                                        "route53:ChangeResourceRecordSetsActions": [
                                            "UPSERT"
                                        ],
                                        "route53:ChangeResourceRecordSetsRecordTypes": [
                                            "A"
                                        ],
                                        RECORD_NAMES_CONDITION_KEY: [
                                            "webhook.olympus.infiquetra.com",
                                            "olympus.infiquetra.com",
                                        ],
                                    }
                                },
                            }
                        ),
                    ]
                )
            },
        },
    )


def test_certbot_policy_limits_parent_zone_changes_to_public_acme_txt() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyName": "home-lab-webhook-certbot-route53",
            "Users": ["letsencrypt-route53"],
            "PolicyDocument": {
                "Statement": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Action": "route53:ChangeResourceRecordSets",
                                "Resource": {
                                    "Fn::Join": Match.array_with(
                                        [
                                            "",
                                            Match.array_with(
                                                [
                                                    "arn:",
                                                    {"Ref": "AWS::Partition"},
                                                    ":route53:::hostedzone/",
                                                    {"Ref": "PublicHostedZoneId"},
                                                ]
                                            ),
                                        ]
                                    )
                                },
                                "Condition": {
                                    "ForAllValues:StringEquals": {
                                        "route53:ChangeResourceRecordSetsRecordTypes": [
                                            "TXT"
                                        ],
                                        RECORD_NAMES_CONDITION_KEY: [
                                            "_acme-challenge.webhooks.infiquetra.com"
                                        ],
                                    }
                                },
                            }
                        )
                    ]
                )
            },
        },
    )


def test_ddns_policy_does_not_allow_wildcard_record_changes() -> None:
    template = synth_template()

    for policy_document in policy_documents(template):
        for statement in policy_document["Statement"]:
            actions = normalize_list(statement["Action"])
            if "route53:ChangeResourceRecordSets" not in actions:
                continue

            assert statement["Resource"] != "*"
            assert statement["Condition"]["ForAllValues:StringEquals"][
                RECORD_NAMES_CONDITION_KEY
            ]
