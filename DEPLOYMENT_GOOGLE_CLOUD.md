# Aureon on Google Cloud

The complete enhanced workspace is deployed to Compute Engine in project
`aureon-trading`. The VM is `aureon-sero-20260906`, zone `europe-west1-b`, with
2 vCPUs, 8 GiB RAM and a 50 GB persistent disk. Its boot disk is retained if
the VM is deleted. The original Windows workspace has not been modified.

[Open the VM](https://console.cloud.google.com/compute/instancesDetail/zones/europe-west1-b/instances/aureon-sero-20260906?project=aureon-trading).

## Complete restoration and credentials

All **42,114 files / 5,137,430,459 bytes** from the encrypted workspace release
were restored to `/srv/aureon/runtime/workspace`. AES-GCM authentication and
every file checksum passed; no files were unavailable. This includes the
original credential files, saved state, private records, logs, binary assets
and embedded Git history.

The recovery key is stored in Google Secret Manager as
`aureon-sero-workspace-recovery`. Its transfer used RSA-OAEP encryption; the
plaintext key was not printed or written into shell commands. The restoration
process received it through stdin. The VM has no Google service account.

Original credential files remain in the restored workspace. They have not been
individually migrated into Secret Manager, and exchange credential validity has
not been tested. The browsable GitHub source continues to redact credentials.

The five original files replaced by Linux compatibility and commissioning
changes are retained under `/srv/aureon/import/pre-cloud-overlay`; the complete
encrypted snapshot also remains under `/srv/aureon/import` and on GitHub.

## Runtime profile

Twelve registry-owned services run under systemd and are enabled at boot:
real-time data feeder, Schumann daemon, planetary monitor, solar collector,
space weather, autonomous health checks, radar signal bridge, HNC core, soul
protection daemon, neural canvas, native Queen mind and heartbeat scheduler.
`cloud_organ.py` defines the exact service names and supervision contract.

The deployment sets `AUREON_DEPLOYMENT_HOLD=1`. This is an additional host gate:
restored capital-release flags do not enable trading; the radar bridge does not
launch an exchange script or replay imported signals as fresh observations.
Code execution, process-control grants and outbound communication stay held
during commissioning. Native reasoning and public data collection operate.

Three registered components are included but inactive:

| Component | Current reason |
|---|---|
| Live radar suite | Trading remains on HOLD |
| Mind thought/action hub | Separate action endpoint activation is pending |
| Self-questioning AI | Requires Ollama; the active native Queen does not |

No exchange orders were placed as part of deployment. Running processes and
source-preserved scientific descriptions are not validation of trading returns
or scientific claims.

## Verified checks

- Complete archive authentication and 42,114 restored file checksums passed.
- Linux dependency installation and `pip check` passed.
- Five regression tests passed locally and on the VM, including restored live
  approvals, prohibited process launches, public-data gates and signal replay.
- All twelve configured processes were live; HNC, Queen and public data files
  had fresh updates.
- The active SQLite memory database returned `ok` from `PRAGMA quick_check`;
  newly written HNC records were read back.
- The dashboard returned HTTP 200 and its live event stream rendered in Chrome.

## Private access

The VM uses its own network. Incoming SSH is limited to Google's IAP range;
there is no public dashboard listener or HTTP firewall rule. The neural canvas
binds to `127.0.0.1:13012` on the VM.

Run this in authenticated Cloud Shell, then choose **Web Preview → port 8080**:

```sh
gcloud compute ssh aureon-sero-20260906 \
  --project=aureon-trading --zone=europe-west1-b --tunnel-through-iap \
  -- -N -L 8080:127.0.0.1:13012 -o ExitOnForwardFailure=yes
```

The preview depends on the Cloud Shell session. The VM services continue to run
when the browser or Cloud Shell closes. For an administrative shell, omit the
arguments after `--tunnel-through-iap`.

Useful commands on the VM:

```sh
sudo systemctl --no-pager list-units 'aureon-organ@*'
sudo journalctl -u aureon-organ@hnc_core.service --no-pager -n 30
```

Organ output is also retained in the workspace `logs` directory. Reproducible
provisioning, restoration, hold tests and service setup live in
[`deployment/google-cloud`](deployment/google-cloud/).

Google's reference: [SSH through IAP](https://docs.cloud.google.com/compute/docs/connect/ssh-using-iap).
