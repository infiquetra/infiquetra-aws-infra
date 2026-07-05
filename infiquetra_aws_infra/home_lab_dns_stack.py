"""Home-lab public DNS access for Route 53 DDNS automation."""

from typing import Any

from aws_cdk import CfnOutput, CfnParameter, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

OLYMPUS_HOSTED_ZONE_ID = "Z0074496WS5CEFE97RIR"
DDNS_USER_NAME = "home-lab-route53-ddns"
CERTBOT_USER_NAME = "letsencrypt-route53"
RECORD_NAMES_CONDITION_KEY = "route53:ChangeResourceRecordSetsNormalizedRecordNames"

PUBLIC_WEBHOOK_RECORD = "webhooks.infiquetra.com"
PUBLIC_WEBHOOK_ACME_RECORD = f"_acme-challenge.{PUBLIC_WEBHOOK_RECORD}"
LEGACY_OLYMPUS_RECORDS = (
    "webhook.olympus.infiquetra.com",
    "olympus.infiquetra.com",
)


class HomeLabDnsStack(Stack):
    """Least-privilege IAM for home-lab Route 53 dynamic DNS updates."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)

        public_hosted_zone_id = CfnParameter(
            self,
            "PublicHostedZoneId",
            type="String",
            description=(
                "Hosted zone ID for infiquetra.com. Used only in the IAM "
                "policy resource ARN; the live A record value is owned by "
                "the home-lab DDNS updater."
            ),
        )

        ddns_user = iam.User(
            self,
            "HomeLabRoute53DdnsUser",
            user_name=DDNS_USER_NAME,
        )

        public_zone_arn = self._hosted_zone_arn(public_hosted_zone_id.value_as_string)
        olympus_zone_arn = self._hosted_zone_arn(OLYMPUS_HOSTED_ZONE_ID)

        ddns_user.attach_inline_policy(
            iam.Policy(
                self,
                "HomeLabRoute53DdnsPolicy",
                policy_name="home-lab-route53-ddns",
                statements=[
                    iam.PolicyStatement(
                        actions=["route53:ListResourceRecordSets"],
                        resources=[public_zone_arn, olympus_zone_arn],
                    ),
                    iam.PolicyStatement(
                        actions=["route53:GetChange"],
                        resources=[f"arn:{self.partition}:route53:::change/*"],
                    ),
                    self._change_record_statement(
                        zone_arn=public_zone_arn,
                        record_names=(PUBLIC_WEBHOOK_RECORD,),
                    ),
                    self._change_record_statement(
                        zone_arn=olympus_zone_arn,
                        record_names=LEGACY_OLYMPUS_RECORDS,
                    ),
                ],
            )
        )

        iam.CfnPolicy(
            self,
            "HomeLabWebhookCertbotRoute53Policy",
            policy_name="home-lab-webhook-certbot-route53",
            users=[CERTBOT_USER_NAME],
            policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "route53:ChangeResourceRecordSets",
                        "Resource": public_zone_arn,
                        "Condition": {
                            "ForAllValues:StringEquals": {
                                "route53:ChangeResourceRecordSetsRecordTypes": ["TXT"],
                                RECORD_NAMES_CONDITION_KEY: [
                                    PUBLIC_WEBHOOK_ACME_RECORD
                                ],
                            }
                        },
                    }
                ],
            },
        )

        CfnOutput(
            self,
            "HomeLabRoute53DdnsUserName",
            value=ddns_user.user_name,
            description=(
                "IAM user for home-lab Route 53 DDNS. Create access keys "
                "manually and store them in the home-lab Ansible vault."
            ),
        )
        CfnOutput(
            self,
            "HomeLabRoute53DdnsPublicRecord",
            value=PUBLIC_WEBHOOK_RECORD,
            description="Primary public webhook ingress record updated by DDNS.",
        )

    def _hosted_zone_arn(self, hosted_zone_id: str) -> str:
        return f"arn:{self.partition}:route53:::hostedzone/{hosted_zone_id}"

    def _change_record_statement(
        self,
        *,
        zone_arn: str,
        record_names: tuple[str, ...],
    ) -> iam.PolicyStatement:
        return iam.PolicyStatement(
            actions=["route53:ChangeResourceRecordSets"],
            resources=[zone_arn],
            conditions={
                "ForAllValues:StringEquals": {
                    "route53:ChangeResourceRecordSetsActions": ["UPSERT"],
                    "route53:ChangeResourceRecordSetsRecordTypes": ["A"],
                    RECORD_NAMES_CONDITION_KEY: list(record_names),
                }
            },
        )
