# Round 3 plan

## Classification

- F1: MUST_FIX — Fix the naming helper to only catch ModuleNotFoundError for infiquetra_aws_infra.naming and re-raise other import errors. Add missing test coverage for error cases. → file(s): infiquetra_aws_infra/constructs/secure_bucket.py, tests/test_secure_bucket.py, est lines: 15
- F2: REVIEWER_ERROR — Reviewer claimed tests are overbuilt but they appropriately test different scenarios of the naming helper functionality. Will not change code.
- F3: MUST_FIX — Fix the exception handling to only catch ModuleNotFoundError specifically for infiquetra_aws_infra.naming instead of broad ImportError to match the approved plan. → file(s): infiquetra_aws_infra/constructs/secure_bucket.py, est lines: 6
- F4: MUST_FIX — Fix the broad exception handling that masks real import-time failures in infiquetra_aws_infra.naming by using specific ModuleNotFoundError handling. → file(s): infiquetra_aws_infra/constructs/secure_bucket.py, est lines: 6
- F5: MUST_FIX — Fix AC1 compliance by making the helper lookup only fall back for ModuleNotFoundError on infiquetra_aws_infra.naming or missing resource_name symbol, not all ImportErrors. → file(s): infiquetra_aws_infra/constructs/secure_bucket.py, est lines: 6

## Budget check

- Total est lines: 33
- Files touched: infiquetra_aws_infra/constructs/secure_bucket.py, tests/test_secure_bucket.py
- Within R3 budget? YES

## Verification commands to run after fix

- pytest tests/test_secure_bucket.py
- ruff check infiquetra_aws_infra/constructs/secure_bucket.py