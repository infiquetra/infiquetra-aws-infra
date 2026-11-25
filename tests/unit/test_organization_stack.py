"""Unit tests for the Infiquetra AWS Organizations stack."""

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.organization_stack import OrganizationStack


def synth_template() -> Template:
    app = App()
    stack = OrganizationStack(
        app,
        "TestOrganizationStack",
        env=Environment(account="645166163764", region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_campps_staging_ou_exists_under_campps() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Organizations::OrganizationalUnit",
        {
            "Name": "Staging",
            "ParentId": {"Ref": Match.string_like_regexp("AppsCamppsOU.*")},
            "Tags": Match.array_with(
                [
                    {"Key": "AccountType", "Value": "PreProduction"},
                    {"Key": "Environment", "Value": "Staging"},
                    {"Key": "Project", "Value": "CAMPPS"},
                ]
            ),
        },
    )


def test_campps_staging_account_is_created_in_staging_ou() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Organizations::Account",
        {
            "AccountName": "campps-staging",
            "Email": "jeff+campps-staging@infiquetra.com",
            "ParentIds": [{"Ref": Match.string_like_regexp("CamppsStagingOU.*")}],
            "RoleName": "OrganizationAccountAccessRole",
            "Tags": Match.array_with(
                [
                    {"Key": "AccountType", "Value": "PreProduction"},
                    {"Key": "BusinessUnit", "Value": "Apps"},
                    {"Key": "Environment", "Value": "Staging"},
                    {"Key": "ManagedBy", "Value": "CDK"},
                    {"Key": "Project", "Value": "CAMPPS"},
                ]
            ),
        },
    )


def test_nonproduction_cost_control_targets_nonprod_and_staging() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Organizations::Policy",
        {
            "Name": "NonProductionCostControl",
            "TargetIds": Match.array_with(
                [
                    {"Ref": Match.string_like_regexp("CamppsNonProdOU.*")},
                    {"Ref": Match.string_like_regexp("CamppsStagingOU.*")},
                    {"Ref": Match.string_like_regexp("CaliberNonProdOU.*")},
                ]
            ),
        },
    )


def test_base_security_allows_cdk_execution_role_policy_cleanup() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Organizations::Policy",
        {
            "Name": "BaseSecurityPolicy",
            "Content": Match.object_like(
                {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Sid": "RequireMFAForSensitiveActions",
                                    "Condition": {
                                        "BoolIfExists": {
                                            "aws:MultiFactorAuthPresent": "false"
                                        },
                                        "ArnNotLike": {
                                            "aws:PrincipalARN": (
                                                "arn:*:iam::*:role/cdk-hnb659fds-cfn-exec-role-*-*"
                                            )
                                        },
                                    },
                                }
                            )
                        ]
                    )
                }
            ),
        },
    )


def test_campps_staging_outputs_exist() -> None:
    template_json = synth_template().to_json()
    outputs = template_json["Outputs"]

    assert "CamppsStagingOUId" in outputs
    assert "CamppsStagingAccountId" in outputs


def test_caliber_nonprod_ou_and_account_exist_under_apps() -> None:
    template = synth_template()
    template_json = template.to_json()

    template.has_resource_properties(
        "AWS::Organizations::OrganizationalUnit",
        {
            "Name": "Caliber",
            "ParentId": {"Ref": Match.string_like_regexp("AppsOU.*")},
            "Tags": Match.array_with(
                [
                    {"Key": "BusinessUnit", "Value": "Apps"},
                    {"Key": "Project", "Value": "Caliber"},
                ]
            ),
        },
    )
    template.has_resource_properties(
        "AWS::Organizations::OrganizationalUnit",
        {
            "Name": "NonProd",
            "ParentId": {"Ref": Match.string_like_regexp("AppsCaliberOU.*")},
            "Tags": Match.array_with(
                [
                    {"Key": "AccountType", "Value": "NonProduction"},
                    {"Key": "Environment", "Value": "NonProd"},
                    {"Key": "Project", "Value": "Caliber"},
                ]
            ),
        },
    )
    template.has_resource_properties(
        "AWS::Organizations::Account",
        {
            "AccountName": "caliber-nonprod",
            "Email": "jeff+caliber-nonprod@infiquetra.com",
            "ParentIds": [{"Ref": Match.string_like_regexp("CaliberNonProdOU.*")}],
            "RoleName": "OrganizationAccountAccessRole",
            "Tags": Match.array_with(
                [
                    {"Key": "AccountType", "Value": "NonProduction"},
                    {"Key": "BusinessUnit", "Value": "Apps"},
                    {"Key": "Environment", "Value": "NonProd"},
                    {"Key": "ManagedBy", "Value": "CDK"},
                    {"Key": "Project", "Value": "Caliber"},
                ]
            ),
        },
    )

    account_resource = next(
        resource
        for resource in template_json["Resources"].values()
        if resource["Type"] == "AWS::Organizations::Account"
        and resource["Properties"]["AccountName"] == "caliber-nonprod"
    )
    assert account_resource["DeletionPolicy"] == "Retain"

    outputs = template_json["Outputs"]
    assert "CaliberOUId" in outputs
    assert "CaliberNonProdOUId" in outputs
    assert "CaliberNonProdAccountId" in outputs
    assert "CaliberNonProdBudgetName" in outputs


def test_caliber_nonprod_has_50_dollar_monthly_budget_alarm() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::Budgets::Budget",
        {
            "Budget": {
                "BudgetName": "caliber-nonprod-monthly-50",
                "BudgetType": "COST",
                "TimeUnit": "MONTHLY",
                "BudgetLimit": {"Amount": 50, "Unit": "USD"},
                "CostFilters": {
                    "LinkedAccount": [
                        {
                            "Fn::GetAtt": [
                                Match.string_like_regexp("CaliberNonProdAccount.*"),
                                "AccountId",
                            ]
                        }
                    ]
                },
            },
            "NotificationsWithSubscribers": Match.array_with(
                [
                    {
                        "Notification": {
                            "ComparisonOperator": "GREATER_THAN",
                            "NotificationType": notification_type,
                            "Threshold": threshold,
                            "ThresholdType": "PERCENTAGE",
                        },
                        "Subscribers": [
                            {
                                "Address": "jeff@infiquetra.com",
                                "SubscriptionType": "EMAIL",
                            }
                        ],
                    }
                    for notification_type in ("ACTUAL", "FORECASTED")
                    for threshold in (50, 80, 100)
                ]
            ),
        },
    )
