# Google Cloud deployment preparation

Target project: `aureon-trading`. The inspected Cloud Run create-service form
uses the GitHub / Cloud Build route, with region `europe-west1`. No service,
build trigger, secret, IAM grant, or trading process was created by this import.

## Credentials are preserved

The encrypted full-workspace backup contains the original credential files.
They also remain in the original local workspace. Restore the backup locally
using `full-workspace-backup/restore_aureon_backup.py` and the separately stored
recovery key when needed. The backup is not a deployable container image.

For deployment, store the selected current credential values in Google Secret
Manager in project `aureon-trading`. In Cloud Run's **Variables & Secrets** tab,
choose **Reference a secret**, preserve the environment-variable names used by
the application, and pin a reviewed secret version. Grant the chosen Cloud Run
service identity Secret Accessor on the required secrets. Do not put credential
values into source files, Docker build arguments, or container images.

Google's instructions: [Configure Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets).

The local radar environment contains these credential variable names:

```text
CAPITAL_API_KEY
CAPITAL_API_PASSWORD
CAPITAL_API_SECRET
CAPITAL_IDENTIFIER
CAPITAL_PASSWORD
CAPITAL_USER
OLLAMA_API_KEY
BINANCE_API_KEY
BINANCE_API_SECRET
KRAKEN_API_KEY
KRAKEN_API_SECRET
APCA_API_KEY_ID
APCA_API_SECRET_KEY
```

Select the actual current environment file for each component before importing
values: the backup preserves historical copies as well. This import did not
test credential validity or make exchange requests.

`CAPITAL_DEMO`, `CAPITAL_DEMO_MODE`, `BINANCE_TESTNET`,
`KRAKEN_LIVE_ENABLED`, and `APCA_LIVE` are runtime controls, not credentials.
Review them explicitly; uploading source does not authorize live orders.

## Deployment work still required

- The repository contains several projects, not a single root-level Cloud Run
  application. Select the HTTP/API component and its build context first.
- `aureon-trading/Dockerfile` refers to `requirements.txt` in that directory,
  which was absent from the supplied source. It also uses older autonomous
  trading startup paths. It has not been validated for the enhanced Fusion stack.
- `aureon-os-upstream/Dockerfile` is a protected bootstrap preflight; its
  entrypoint is not a long-running Cloud Run HTTP service.
- Fusion uses Windows workspace defaults, a local Ollama model, background
  processes, and mutable local state. Configure Linux paths with
  `SERO_WORKSPACE`, supply the model runtime, and choose durable storage and
  a single owner for each background process before running it in the cloud.
- A Cloud Run service must listen on `0.0.0.0:$PORT`; its ordinary writable
  filesystem is not durable. Review the [Cloud Run container contract](https://docs.cloud.google.com/run/docs/container-contract).
- The inspected create form defaults to request-based billing and zero minimum
  instances. Those settings do not establish continuous operation for this
  daemon-oriented workspace. Choose a suitable runtime architecture and resource
  budget before creating a service or worker.

The encrypted backup is excluded from Docker and gcloud build contexts so that
building an application does not bake its full private archive into an image.
