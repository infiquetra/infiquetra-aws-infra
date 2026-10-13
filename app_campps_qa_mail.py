#!/usr/bin/env python3
"""CDK app for the team-hermod QA inbound mail stack (CAMPPS nonprod only).

Not part of deploy-infrastructure.yml (management account only); deploy manually:
    cdk -a "python3 app_campps_qa_mail.py" deploy CamppsQaMailStack \
        --profile campps-nonprod
"""

from aws_cdk import App, Environment
from dotenv import load_dotenv

from infiquetra_aws_infra.campps_qa_mail_stack import (
    QA_MAIL_ACCOUNT_ID,
    QA_MAIL_REGION,
    CamppsQaMailStack,
)

load_dotenv()

app = App()

CamppsQaMailStack(
    app,
    "CamppsQaMailStack",
    env=Environment(account=QA_MAIL_ACCOUNT_ID, region=QA_MAIL_REGION),
    description="SES inbound catch-all for qa.infiquetra.com QA test mail (nonprod)",
)

app.synth()
