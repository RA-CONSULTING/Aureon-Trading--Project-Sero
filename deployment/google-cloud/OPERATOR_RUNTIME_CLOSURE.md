# VM operator runtime closure

The VM operator release is bound to the complete tracked
`aureon-os-upstream/aureon` Python package. A short list of files imported
directly by `operator_server.py` is insufficient because route registration,
lazy package exports, the connectome, and several registries load modules
transitively or from data-driven names.

`operator_runtime_closure.py` classifies the source set without importing it.
The release builder must obtain the package inventory from the selected Git
revision, require every classified source in the reviewed payload, and add the
returned closure object to `manifest.json`. The updater validates that object
and its payload hashes before stopping a service. It also treats any existing
package `.py` file absent from the declared closure as stale source and removes
it in the same rollback-capable transaction. This prevents a deleted module
from being imported from an older VM checkout while the service reports the new
revision.

The source closure contains all tracked package `.py` files, explicitly
classified immutable package assets, a finite companion-module set, and the
hardened VM entry shims. Tracked plans and cache snapshots remain outside it.
Unknown package assets fail the build until classified. `.env`, credentials,
ledgers, databases, logs, caches, and other runtime state are never inferred
from directory contents.

The companion list is checked by a recursive, import-free AST walk over every
tracked package module. It follows absolute and relative imports plus literal
`import_module`/`__import__` calls through repository-local modules. Because
the complete package is selected, data-driven imports within `aureon` cannot
resolve to an omitted old package file; a newly discovered repository-local
companion fails the regression until it is reviewed and classified.

Apply stops the selected services before purging `.pyc`, `.pyo`, and
`__pycache__` files. Stale package `.py` removal is an ordinary journal entry:
its previous bytes, mode, and owner are backed up, and rollback restores that
one file. The updater also journals every source parent directory, installs
source as `root:root` without file write bits, and makes every source ancestor
`root:root` without group/other write bits. Directory metadata is restored on
rollback. A committed check rejects a writable/non-root file or ancestor, a
new stale package module, or remaining bytecode.

This closure applies only to the held VM operator/read plane. It does not alter
the reviewed eight-module Cloud Run trading image. The VM service must continue
to start through `sitecustomize.py` and `cloud_credential_boundary.py`, with the
deployment hold, disabled exchange mutations, safe exchange modes, and no
exchange credential bundle.

## VM process and Google identity boundary

The updater renders the operator as `aureon-operator`, the UI as `aureon-ui`,
the receipt/intent bridge as `aureon-trade-bridge`, provider readers as
`aureon-provider`, and every ordinary read organ under its own bounded dynamic
UID. Each unit has a private systemd state/cache directory, no writable source
path, `ProtectProc=invisible`, and `ProcSubset=pid`. The operator keystore is
under its private 0700 state directory. Only the release-ledger and sanitized
trade-readback subdirectories cross the operator/trade boundary, through the
commissioned `aureon-control-readers` group with one writer per subdirectory.

Every workload unit denies `169.254.169.254/32` and `fd20:ce::254/128`.
Google-bound units consume only their fixed, broker-rotated token file and set
`AUREON_VM_TOKEN_BROKER_REQUIRED=1`; the public VM bridge denies metadata too.
The sole metadata consumer is the root-owned
`aureon-cloud-token-broker.service`. Its attached
`aureon-vm-token-broker@aureon-trading.iam.gserviceaccount.com` identity must
have no data-plane role and may impersonate only the four workload identities
enumerated in `trading-control/resource_contract.json`. The exact per-resource
capabilities in that commissioning contract are the maximum IAM surface.

Until provider readback proves that broker identity is the VM's sole attached
service account, that the old shared runtime identity has no data-plane roles,
and that every workload has both metadata denies, the previous single-service-
account union remains a production blocker. Local unit rendering and tests do
not prove that external IAM state.

The operator unit also requires the canonical Supabase owner UUID and the
lowercase SHA-256 commitment of the provider-confirmed email as one atomic
configuration pair. The release journal and unit contain the UUID and digest;
the plaintext owner email is never accepted or stored.
