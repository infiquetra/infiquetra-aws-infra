# QA inbound mail (SES on qa.infiquetra.com)

Disposable test inboxes for the team-hermod QA agents. Any address
`<anything>@qa.infiquetra.com` is accepted by SES in **campps-nonprod
(477152411873), us-east-1** and stored raw (MIME) in S3. The root `infiquetra.com`
MX (Google Workspace) is not touched.

| Piece | Value |
|---|---|
| CDK app / stack | `app_campps_qa_mail.py` / `CamppsQaMailStack` |
| Bucket | `infiquetra-campps-qa-mail-477152411873` (SSE-S3, public access blocked, TLS-only, 7-day expiration) |
| Object prefix | `inbound/` (object key = SES message ID) |
| SES identity | domain `qa.infiquetra.com` (Easy DKIM) |
| Receipt rule set / rule | `campps-qa-inbound` / `qa-catch-all-to-s3` (recipient `qa.infiquetra.com`, spam/virus scan on) |
| Agent access | `CAMPPSQAReadOnly`: `s3:GetObject` + `s3:ListBucket` on this bucket only |

## Deploy (not covered by CI)

`deploy-infrastructure.yml` only deploys the management-account `app.py`
(Organization + SSO). This stack is a separate app, like `app_campps_bootstrap.py`,
and must be deployed by hand with nonprod admin credentials.

1. Deploy the mail stack:
   ```bash
   cdk -a "python3 app_campps_qa_mail.py" diff   CamppsQaMailStack --profile campps-nonprod
   cdk -a "python3 app_campps_qa_mail.py" deploy CamppsQaMailStack --profile campps-nonprod
   ```
2. Activate the rule set (CloudFormation has no resource for this; only one rule set
   can be active per account and Region). First check that nothing else is active:
   ```bash
   aws ses describe-active-receipt-rule-set --region us-east-1 --profile campps-nonprod
   aws ses set-active-receipt-rule-set --rule-set-name campps-qa-inbound \
     --region us-east-1 --profile campps-nonprod
   ```
   If another rule set is already active, **stop**: activating this one would disable it.
   Add the rule to the existing set instead.
3. Add DNS records in the `infiquetra.com` hosted zone (management account
   645166163764; the repo has no cross-account DNS automation). Take the DKIM values
   from the stack outputs `QaMailDkimCname1..3`:
   | Name | Type | Value |
   |---|---|---|
   | `qa.infiquetra.com` | MX | `10 inbound-smtp.us-east-1.amazonaws.com` |
   | `<token1>._domainkey.qa.infiquetra.com` | CNAME | `<token1>.dkim.amazonses.com` |
   | `<token2>._domainkey.qa.infiquetra.com` | CNAME | `<token2>.dkim.amazonses.com` |
   | `<token3>._domainkey.qa.infiquetra.com` | CNAME | `<token3>.dkim.amazonses.com` |
4. Wait until `aws sesv2 get-email-identity --email-identity qa.infiquetra.com` shows
   `VerifiedForSendingStatus: true`. Then send a test message from any mailbox and
   look for `inbound/<message-id>` in the bucket.
5. The `CAMPPSQAReadOnly` change ships with the SSO stack (automatic deploy on main).

## Pitfalls
- **Sandbox does not matter for receiving.** It only limits *sending*.
- **Unverified domain / no active rule set.** SES rejects mail for recipients that
  no active receipt rule matches. Both steps 2 and 4 must be done.
- **Bucket policy.** SES checks write access when the rule is created, so the
  bucket policy is created first (explicit dependency).
- **Size.** S3 delivery accepts messages up to 40 MB including headers.
- **MX.** Only `qa.infiquetra.com` gets an MX. Do not add a wildcard MX.
- **PII.** Data is test-only and expires after 7 days. Don't forward it anywhere else.

## Cost
About $0: SES inbound is $0.10 per 1,000 emails plus $0.09 per 1,000 incoming
256 KB chunks. S3 storage for 7 days of test mail costs pennies.
