"""Unit tests for the Infiquetra Identity Center stack."""

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template

from infiquetra_aws_infra.organization_stack import OrganizationStack
from infiquetra_aws_infra.sso_stack import SSOStack


def synth_template() -> Template:
    app = App()
    organization_stack = OrganizationStack(
        app,
        "TestOrganizationStack",
        env=Environment(account="645166163764", region="us-east-1"),
    )
    sso_stack = SSOStack(
        app,
        "TestSSOStack",
        organization_stack=organization_stack,
        env=Environment(account="645166163764", region="us-east-1"),
    )
    return Template.from_stack(sso_stack)


def test_campps_developer_permission_set_uses_correct_name() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SSO::PermissionSet",
        {
            "Name": "CAMPPSDeveloper",
            "ManagedPolicies": ["arn:aws:iam::aws:policy/PowerUserAccess"],
        },
    )


def test_prod_breakglass_permission_set_exists() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SSO::PermissionSet",
        {
            "Name": "CAMPPSProductionBreakGlassAdministrator",
            "SessionDuration": "PT4H",
            "ManagedPolicies": ["arn:aws:iam::aws:policy/AdministratorAccess"],
        },
    )


def test_optional_group_parameters_exist() -> None:
    template = synth_template()

    template.has_parameter("InfiquetraAdminsGroupId", {"Type": "String", "Default": ""})
    template.has_parameter("CamppsDevelopersGroupId", {"Type": "String", "Default": ""})
    template.has_parameter(
        "CamppsProdReadOnlyGroupId", {"Type": "String", "Default": ""}
    )
    template.has_parameter(
        "CamppsProdBreakGlassAdminsGroupId", {"Type": "String", "Default": ""}
    )


def test_group_assignments_target_expected_accounts() -> None:
    template = synth_template()

    template.resource_count_is("AWS::SSO::Assignment", 4)
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "InfiquetraAdminsGroupId"},
            "TargetId": "645166163764",
            "TargetType": "AWS_ACCOUNT",
        },
    )
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "CamppsDevelopersGroupId"},
            "TargetId": "477152411873",
            "TargetType": "AWS_ACCOUNT",
        },
    )
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "CamppsProdReadOnlyGroupId"},
            "TargetId": "431643435299",
            "TargetType": "AWS_ACCOUNT",
        },
    )
    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalType": "GROUP",
            "PrincipalId": {"Ref": "CamppsProdBreakGlassAdminsGroupId"},
            "TargetId": "431643435299",
            "TargetType": "AWS_ACCOUNT",
        },
    )


def test_group_assignments_are_conditionally_created() -> None:
    template_json = synth_template().to_json()
    assignment_resources = [
        resource
        for resource in template_json["Resources"].values()
        if resource["Type"] == "AWS::SSO::Assignment"
    ]

    assert assignment_resources
    for resource in assignment_resources:
        assert "Condition" in resource
        assert resource["Condition"].endswith("Provided")


def test_core_admin_assignment_uses_core_admin_permission_set() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SSO::Assignment",
        {
            "PrincipalId": {"Ref": "InfiquetraAdminsGroupId"},
            "PermissionSetArn": {
                "Fn::GetAtt": [
                    Match.string_like_regexp("CoreAdminPermissionSet.*"),
                    "PermissionSetArn",
                ]
            },
        },
    )
