"""Generate architecture diagrams for docs/ops/.

Run from repo root:
    uv run python docs/ops/diagrams/generate.py

Requires graphviz binary (brew install graphviz) and the `diagrams` Python
package (already in dev dependencies).

Each `with Diagram(...)` block writes a PNG into docs/ops/diagrams/.
"""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.management import (
    Cloudformation,
    Organizations,
    OrganizationsAccount,
    OrganizationsOrganizationalUnit,
)
from diagrams.aws.security import (
    IAM,
    IAMRole,
    IdentityAndAccessManagementIamPermissions,
)
from diagrams.onprem.client import Client, User
from diagrams.onprem.vcs import Github
from diagrams.programming.framework import (
    React,  # used as a generic CDK stand-in icon
)

OUTPUT_DIR = Path(__file__).parent
GRAPH_ATTR = {
    "fontsize": "14",
    "fontname": "Helvetica",
    "bgcolor": "white",
    "pad": "0.5",
    "splines": "spline",
}
NODE_ATTR = {"fontname": "Helvetica", "fontsize": "12"}
EDGE_ATTR = {"fontname": "Helvetica", "fontsize": "10"}


# ---------------------------------------------------------------------------
# 1. System context — the high-level picture
# ---------------------------------------------------------------------------
with Diagram(
    "Infiquetra AWS — System Context",
    filename=str(OUTPUT_DIR / "01-system-context"),
    show=False,
    direction="LR",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    dev = User("Developer\n(jefcox)")
    repo = Github("infiquetra/\ninfiquetra-aws-infra")

    with Cluster("AWS Organization (645166163764 — root mgmt)"):
        org = Organizations("Organization\nr-f3un")

        with Cluster("Active workload accounts"):
            mgmt = OrganizationsAccount("infiquetra\n645166163764")
            prod = OrganizationsAccount("campps-prod\n431643435299")
            dev_acct = OrganizationsAccount("campps-dev\n477152411873")

        with Cluster("Identity Center (SSO)"):
            sso = IAM("13 Permission Sets\n1 user, 1 group")

        with Cluster("CI/CD federation"):
            oidc = IAMRole("infiquetra-aws-\ninfra-gha-role")

    dev >> Edge(label="aws sso login\n(8h portal session)") >> sso
    sso >> Edge(label="assume role") >> mgmt
    sso >> Edge(label="assume role") >> prod
    sso >> Edge(label="assume role") >> dev_acct

    repo >> Edge(label="GitHub OIDC token", style="dashed") >> oidc
    oidc >> Edge(label="cdk deploy", style="dashed") >> mgmt

    org - Edge(style="invis") - mgmt


# ---------------------------------------------------------------------------
# 2. AWS Organizations — full OU tree (current state with dual CAMPPS)
# ---------------------------------------------------------------------------
with Diagram(
    "AWS Organizations — Current OU Structure",
    filename=str(OUTPUT_DIR / "02-org-structure"),
    show=False,
    direction="TB",
    graph_attr={**GRAPH_ATTR, "ranksep": "0.6", "nodesep": "0.4"},
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    root = Organizations("Root\nr-f3un")
    mgmt_acct = OrganizationsAccount("infiquetra\n645166163764\n(mgmt)")

    # Root-level OUs
    with Cluster("CDK-managed OUs (empty)"):
        core_ou = OrganizationsOrganizationalUnit("Core\nSCP: BaseSecurity")
        media_ou = OrganizationsOrganizationalUnit("Media\nSCP: BaseSecurity")
        consulting_ou = OrganizationsOrganizationalUnit("Consulting\nSCP: BaseSecurity")
        with Cluster("Apps OU"):
            apps_ou = OrganizationsOrganizationalUnit("Apps\nSCP: BaseSecurity")
            with Cluster("CAMPPS (new, empty)"):
                new_campps = OrganizationsOrganizationalUnit("CAMPPS")
                new_prod = OrganizationsOrganizationalUnit("Production")
                new_nonprod = OrganizationsOrganizationalUnit(
                    "NonProd\nSCP: NonProdCostControl"
                )

    with Cluster("Legacy OUs (pre-CDK, no SCP coverage)"):
        legacy_campps = OrganizationsOrganizationalUnit("CAMPPS\n(legacy)")
        with Cluster("workloads"):
            workloads_ou = OrganizationsOrganizationalUnit("workloads")
            prod_ou = OrganizationsOrganizationalUnit("PRODUCTION")
            sdlc_ou = OrganizationsOrganizationalUnit("SDLC")
        with Cluster("CICD (empty)"):
            cicd_ou = OrganizationsOrganizationalUnit("CICD")
            cicd_prod = OrganizationsOrganizationalUnit("PRODUCTION\n(empty)")

    prod_acct = OrganizationsAccount("campps-prod\n431643435299")
    dev_acct = OrganizationsAccount("campps-dev\n477152411873")

    root >> mgmt_acct
    root >> core_ou
    root >> media_ou
    root >> consulting_ou
    root >> apps_ou
    root >> legacy_campps

    apps_ou >> new_campps
    new_campps >> new_prod
    new_campps >> new_nonprod

    legacy_campps >> workloads_ou
    workloads_ou >> prod_ou
    workloads_ou >> sdlc_ou
    prod_ou >> prod_acct
    sdlc_ou >> dev_acct

    legacy_campps >> cicd_ou
    cicd_ou >> cicd_prod


# ---------------------------------------------------------------------------
# 3. Developer SSO login flow
# ---------------------------------------------------------------------------
with Diagram(
    "Developer Login Flow — AWS SSO",
    filename=str(OUTPUT_DIR / "03-developer-login"),
    show=False,
    direction="LR",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    dev = User("Developer\n(jefcox)")

    with Cluster("Local machine"):
        cli = Client("aws CLI\n(profile:\ninfiquetra-root)")
        browser = Client("Browser\n(d-90676975b4\n.awsapps.com)")

    with Cluster("AWS Identity Center"):
        portal = IdentityAndAccessManagementIamPermissions(
            "SSO portal\n(8h interactive,\n7d background)"
        )
        ps_admin = IAM("AdministratorAccess\n(legacy, PT12H,\nattached to all 3 accts)")

    with Cluster("AWS Accounts"):
        mgmt = OrganizationsAccount("infiquetra\n645166163764")
        prod = OrganizationsAccount("campps-prod\n431643435299")
        dev_acct = OrganizationsAccount("campps-dev\n477152411873")

    dev >> Edge(label="1. aws sso login") >> cli
    cli >> Edge(label="2. open browser") >> browser
    browser >> Edge(label="3. authenticate") >> portal
    portal >> Edge(label="4. issue OIDC token") >> cli
    cli >> Edge(label="5. assume role via\nGetRoleCredentials") >> ps_admin
    ps_admin >> Edge(label="6. STS creds") >> cli
    cli >> Edge(style="dashed") >> mgmt
    cli >> Edge(style="dashed") >> prod
    cli >> Edge(style="dashed") >> dev_acct


# ---------------------------------------------------------------------------
# 4. GitHub Actions OIDC flow
# ---------------------------------------------------------------------------
with Diagram(
    "GitHub Actions Auth Flow — OIDC Federation",
    filename=str(OUTPUT_DIR / "04-gha-oidc-flow"),
    show=False,
    direction="LR",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    push = Github("Push to\nmain branch")

    with Cluster("GitHub Actions runner"):
        wf = Cloudformation("deploy-\ninfrastructure\n.yml")
        oidc_token = IAM("GitHub OIDC token\nsub=repo:infiquetra/*")

    with Cluster("AWS account 645166163764"):
        provider = IAM("OIDC provider\ntoken.actions.\ngithubusercontent.com")
        role = IAMRole(
            "infiquetra-aws-\ninfra-gha-role\n(7 managed policies,\nmax 12h)"
        )
        cfn = Cloudformation("CloudFormation\nOrg + SSO stacks")

    push >> Edge(label="trigger") >> wf
    wf >> Edge(label="request token") >> oidc_token
    oidc_token >> Edge(label="present + verify") >> provider
    provider >> Edge(label="trust check\nrepo:infiquetra/*") >> role
    role >> Edge(label="STS\nAssumeRoleWith\nWebIdentity") >> wf
    wf >> Edge(label="cdk deploy", style="dashed") >> cfn


# ---------------------------------------------------------------------------
# 5. CI/CD pipeline architecture (composite + reusable workflows)
# ---------------------------------------------------------------------------
with Diagram(
    "CI/CD Pipeline Architecture",
    filename=str(OUTPUT_DIR / "05-cicd-pipeline"),
    show=False,
    direction="TB",
    graph_attr=GRAPH_ATTR,
    node_attr=NODE_ATTR,
    edge_attr=EDGE_ATTR,
):
    pr = Github("Pull Request\nto main")
    push = Github("Push to main")

    with Cluster("Main workflows"):
        prv = Cloudformation("pull-request-\nvalidation.yml")
        di = Cloudformation("deploy-\ninfrastructure.yml")

    with Cluster("Reusable workflows"):
        cq = React("reusable-code-\nquality.yml\n(ruff, mypy)")
        ss = React("reusable-security-\nscan.yml\n(bandit, semgrep,\ncheckov)")
        cs = React("reusable-cdk-\nsynthesis.yml\n(synth, cfn-lint)")
        dep = React("reusable-aws-\ndeployment.yml")

    with Cluster("Composite actions"):
        spy = Lambda("setup-python-uv")
        snc = Lambda("setup-node-cdk")
        sac = Lambda("setup-aws-\ncredentials\n(OIDC)")

    with Cluster("AWS"):
        cfn = Cloudformation("CFN stacks +\ngit deploy tag")

    pr >> prv
    push >> di

    prv >> cq
    prv >> ss
    prv >> cs
    di >> dep

    cq >> spy
    ss >> spy
    cs >> spy
    cs >> snc
    dep >> spy
    dep >> snc
    dep >> sac

    sac >> Edge(label="OIDC", style="dashed") >> cfn
    dep >> Edge(label="cdk deploy", style="dashed") >> cfn


print("Generated 5 diagrams:")
for f in sorted(OUTPUT_DIR.glob("*.png")):
    print(f"  {f.name}")
