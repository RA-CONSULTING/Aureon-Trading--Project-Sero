# Cloud coding organism route

The owner coding cockpit reads `GET /api/coding/status` through the same-origin
operator API. The Cloud Run owner entry requires IAP, the private bridge binds
the request to the fixed loopback operator, and the operator route requires the
admin identity again. Tenant accounts are denied by the operator's default-deny
route table.

The current receipt reports `coding_service_not_commissioned`. This is the live
state of the cloud coding capability. The local mind hub is deliberately not
started or proxied because it contains repo-writing, autonomous-job, reload and
other action handlers. The cloud route registers no prompt, chat, reload, job,
arbitrary destination or credential endpoint.

The status request is passive and passes through the existing operator identity
gate. Any future mutating API would also enter the operator HNC boundary and
would need an exact signed cloud-intent route in both bridge and operator
custody. No such coding-action route or signing rule exists in this release, so
those requests fail closed before an action handler can run.

A future coding worker requires a separate reviewed service and custody
contract. It must provide current, verifiable readiness and narrow action
receipts before any capability can change from unavailable. An environment flag
or an old generated JSON file is not commissioning evidence.
