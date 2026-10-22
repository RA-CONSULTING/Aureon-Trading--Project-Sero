# Keys to rotate

Scan of the now-public Sero repository `RA-CONSULTING/Aureon-Trading--Project-Sero` on 22 Oct 2026, 22:05 Europe/London.

Scanners, over every local branch and tag (`main`, `cursor/aureon-fusion-unify-198b`, `cursor/public-market-observation-befa`, `workspace-2026-09-06`, `workspace-2026-09-07`; 61 commits):

- gitleaks 8.28.0 `detect --log-opts="--all"`
- trufflehog 3.90.1 `git` on each of those refs, with provider verification left off so this scan did not log in anywhere

This file records file, commit, and type only. It does not contain values.

## Must rotate

One Capital.com session login was hardcoded against the live host `api-capital.backend-capital.com`. The same commit added it in two scripts. Those lines are not in the tip of `main`, `cursor/aureon-fusion-unify-198b`, or `cursor/public-market-observation-befa`. The commit is still in the history of `main` and of the staging branch, and it is tag `workspace-2026-09-07`. Treat the values as exposed. Rotate the Capital.com API key and the account password. The login identifier in the same lines is an email address.

| File | Commit | Type | In HEAD |
| --- | --- | --- | --- |
| `aureon_radar/test_epic.py` | `aaea92f354599798979cfb86342ec2e0fae7c9b6` | capital_account_identifier, capital_account_password, capital_api_key | no |
| `aureon_radar/test_order.py` | `aaea92f354599798979cfb86342ec2e0fae7c9b6` | capital_account_identifier, capital_account_password, capital_api_key | no |

## Reviewed and not credentials

Gitleaks reported 34 hits and trufflehog reported unverified detector hits. Inspection showed these are not credentials, so they do not need rotation:

- `.env.example` bind address `AUREON_FUSION_BIND` (empty token and empty exchange key fields).
- Canonical resonance fingerprints in `sources/NEXUS-LIVE-FEED-/` (a published reference fingerprint, not an API or wallet key).
- Python type annotations named like `Ed25519PrivateKey` in the plumber.
- Test fixtures and known-answer vectors, including dummy Kraken probe keys named `dummy_key`, idempotency keys, and short test API strings.
- UI field names, audit allowlist fingerprints, git SHA-1 values misread as GitHub tokens, and fixture URLs.

No `.env` file with a live token is in the branch tips. No wallet private-key block was reported. Trufflehog did not contact providers; the Capital.com set above is real because the scripts posted an identifier, a password, and an API key to the live session endpoint.
