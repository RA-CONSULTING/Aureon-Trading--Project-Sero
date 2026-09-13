# Supabase production cutover

This runbook is pinned to project `siihxcwetdjdsrfdexmb`, Supabase CLI
`2.117.0`, and migration
`20260913101606_harden_user_credential_ownership.sql`.

1. Commit and push the reviewed source first. Run:

   ```powershell
   python scripts/validation/audit_supabase_production_edge_surface.py
   python -m pytest -q tests/test_supabase_edge_auth_contract.py tests/test_supabase_production_edge_attack_surface.py tests/test_supabase_credential_hardening_cutover.py
   ```

2. Capture a fresh provider inventory with `functions list`. Require exactly
   100 active slugs and no difference from the manifest's captured slug,
   version, or JWT baseline before deploying anything.

3. Deploy the 95 retirement stubs first, with one API job and without
   `--no-verify-jwt` or `--prune`:

   ```powershell
   $surface = Get-Content docs/evidence/supabase/edge-functions/20260913/production_attack_surface.json -Raw | ConvertFrom-Json
   $retired = @($surface.retirement_deploy_targets)
   & npx.cmd --yes supabase@2.117.0 functions deploy @retired --project-ref siihxcwetdjdsrfdexmb --use-api --jobs 1
   ```

   Read the inventory again. Require the same 100-slug set, a newer version for
   every retirement target, and `verify_jwt=true` for all 95 before continuing.

4. Deploy the three retained-source hardening targets, then read the inventory
   again:

   ```powershell
   $hardened = @($surface.retained_hardening_deploy_targets)
   & npx.cmd --yes supabase@2.117.0 functions deploy @hardened --project-ref siihxcwetdjdsrfdexmb --use-api --jobs 1
   & npx.cmd --yes supabase@2.117.0 functions list --project-ref siihxcwetdjdsrfdexmb --output-format json
   ```

   Require exactly 100 active slugs; newer versions for all 98 deploy targets;
   exactly 98 routes with JWT verification; and exactly these two without it:
   `fetch-binance-market-data` and `fetch-schumann-data`.

5. Probe every retired route. An unauthenticated request must receive gateway
   `401`. An authenticated request must receive its inert `410` or `503` marker.
   Verify the three hardened public-data routes return their declared provider
   provenance and freshness fields. A missing, stale, or malformed provider
   timestamp must return no-data rather than fresh telemetry.

6. Audit the database using metadata only. It must return `ready_to_apply` with
   `baseline_history_exact=true`:

   ```powershell
   python scripts/operations/supabase_credential_hardening_cutover.py audit --windows-credential-target 'Supabase CLI:supabase'
   ```

7. If the Supabase CLI database login remains unavailable, use the reviewed
   Management API fallback. It submits one transaction, rechecks the exact
   67-row predecessor history under an advisory lock, applies the checked-in
   SQL, validates the effective ACL/policy/RPC/Realtime contract, inserts the
   canonical `version, statements, name` history row, and commits only after
   all checks pass:

   ```powershell
   python scripts/operations/supabase_credential_hardening_cutover.py apply --windows-credential-target 'Supabase CLI:supabase' --acknowledge-sha256 ec9c3f99f024f06904765c6c7805ade8cdfbb52a3613c85192b58d1b477c9c66
   ```

   Never retry an uncertain write. Run audit again. Require `state=applied`,
   `history_present=true`, `history_exact=true`, `target_schema_exact=true`,
   `legacy_schema_exact=false`, policy count `6`, no session Realtime
   membership, and one status RPC. Also GET Management API path
   `/v1/projects/siihxcwetdjdsrfdexmb/database/migrations/20260913101606` and
   require the exact version and name.

8. Produce the owner binding receipt only after the contract values and source
   revision are final. The bootstrap reads the existing Management API token
   from Windows Credential Manager, retrieves the single legacy `service_role`
   key in memory, and pipes it to the provider-readback program on stdin. It
   never writes or prints either credential:

   ```powershell
   python scripts/operations/supabase_owner_readback_via_management.py --subject $ownerSubject --source-revision $sourceRevision --contract-sha256 $contractSha256 --receipt $absoluteReceiptPath
   ```

   A successful receipt has exactly schema
   `aureon.supabase-owner-provider-readback.v1`, provider
   `supabase_auth_admin`, the bound project/subject, app metadata role `owner`,
   confirmed email state, a domain-separated email SHA-256, recorded time,
   source revision, and contract SHA-256. Supply its printed receipt SHA-256 as
   the exact commissioning acknowledgement.

9. Run the Supabase security advisor and classify any new P0/P1 finding before
   promoting the matching frontend and cloud revision.

The checked-in down migration restores browser access to encrypted credential
columns and the session table's Realtime publication. Use it only after public
application ingress is removed and the matching application revision is
restored.
