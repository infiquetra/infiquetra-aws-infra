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
            "Name": "CAMPPSProdBreakGlassAdmin",
            "SessionDuration": "PT4H",
            "ManagedPolicies": ["arn:aws:iam::aws:policy/AdministratorAccess"],
        },
    )


def test_permission_set_names_fit_identity_center_limit() -> None:
    template_json = synth_template().to_json()
    permission_sets = [
        resource["Properties"]
        for resource in template_json["Resources"].values()
        if resource["Type"] == "AWS::SSO::PermissionSet"
    ]

    assert permission_sets
    for permission_set in permission_sets:
        assert len(permission_set["Name"]) <= 32


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

    template.resource_count_is("AWS::SSO::Assignment", 6)
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
            "PrincipalId": {"Ref": "CamppsDevelopersGroupId"},
            "TargetId": {
                "Fn::ImportValue": Match.string_like_regexp(
                    "TestOrganizationStack:ExportsOutputFnGetAttCamppsStagingAccountAccountId.*"
                )
            },
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


def test_campps_qa_permission_set_is_short_lived_view_only() -> None:
    template = synth_template()

    template.has_resource_properties(
        "AWS::SSO::PermissionSet",
        {
            "Name": "CAMPPSQAReadOnly",
            "SessionDuration": "PT1H",
            "ManagedPolicies": ["arn:aws:iam::aws:policy/job-function/ViewOnlyAccess"],
        },
    )


def test_campps_qa_assignment_targets_only_nonprod() -> None:
    template_json = synth_template().to_json()
    resources = template_json["Resources"]
    qa_logical_ids = [
        logical_id
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::SSO::PermissionSet"
        and resource["Properties"]["Name"] == "CAMPPSQAReadOnly"
    ]
    assert len(qa_logical_ids) == 1
    qa_assignments = [
        resource
        for resource in resources.values()
        if resource["Type"] == "AWS::SSO::Assignment"
        and resource["Properties"]["PermissionSetArn"]
        == {"Fn::GetAtt": [qa_logical_ids[0], "PermissionSetArn"]}
    ]

    assert len(qa_assignments) == 1
    assert qa_assignments[0]["Properties"]["TargetId"] == "477152411873"
    assert qa_assignments[0]["Condition"] == "CamppsQaGroupIdProvided"


def _qa_policy_statements() -> list[dict]:
    import json

    resources = synth_template().to_json()["Resources"]
    qa = next(
        r
        for r in resources.values()
        if r["Type"] == "AWS::SSO::PermissionSet"
        and r["Properties"]["Name"] == "CAMPPSQAReadOnly"
    )
    policy = qa["Properties"]["InlinePolicy"]
    policy = json.loads(policy) if isinstance(policy, str) else policy
    statements: list[dict] = policy["Statement"]
    return statements


def test_campps_qa_s3_read_exception_is_limited_to_qa_mail_bucket() -> None:
    bucket_arn = "arn:aws:s3:::infiquetra-campps-qa-mail-477152411873"
    statements = _qa_policy_statements()

    s3_allows = [
        s
        for s in statements
        if s["Effect"] == "Allow" and any(str(a).startswith("s3:") for a in s["Action"])
    ]
    assert len(s3_allows) == 1
    assert sorted(s3_allows[0]["Action"]) == ["s3:GetObject", "s3:ListBucket"]
    assert sorted(s3_allows[0]["Resource"]) == [bucket_arn, f"{bucket_arn}/*"]

    get_object_denies = [
        s
        for s in statements
        if s["Effect"] == "Deny"
        and any(str(a).startswith("s3:GetObject") for a in s["Action"])
    ]
    assert len(get_object_denies) == 1
    assert "Resource" not in get_object_denies[0]
    assert get_object_denies[0]["NotResource"] == [f"{bucket_arn}/*"]
