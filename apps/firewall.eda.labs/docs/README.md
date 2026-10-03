# Firewalls

External firewall endpoints for the `pan-d3l` lab. Palo Alto and FortiGate are
not TopoNodes. Each firewall is a `Firewall` resource. Each NIC is a
`FirewallInterface`. Creating a `FirewallInterface` is how you add an interface.
When `spec.attachment` is set, the config intent also creates the leaf
`Interface` that faces that NIC and labels it with the VNET.

| Endpoint | Management | Inside | Outside |
|----------|------------|--------|---------|
| `palo-alto` | `https://100.124.186.51:8444` | `ethernet1/1` `10.31.1.1/24` on `pan-inside` | `ethernet1/2` `10.31.2.1/24` on `pan-outside` |
| `fortigate` | `https://100.124.186.50:8443` | `port2` `10.21.0.1/24` on `fg-inside` | `port3` `10.22.0.1/24` on `fg-outside` |

Credentials stay in Secrets (`username`, `password`). Examples use `replace-me`.

Firewall communication is the vendor API only. Palo Alto uses the XML API
(`/api/`). FortiGate uses the REST API (`/api/v2`). `fwstatus` reads health,
version, serial, license, and interface state from those APIs, and pushes a
NIC address, ping, admin state, or zone only when the API state differs.
There is no firewall CLI or SSH session.

`fwstatus` uses the EDA SDK (`eda.dev/edk`) Kubernetes client to write
`.status` (health, version, serial, license, and the networking rollup).
Inside the cluster, `FWSTATUS_STATE_DB=1` also publishes that status to the
state aggregator. Do not set that flag outside the cluster.

```bash
go run ./cmd/fwstatus -namespace clab-pan-d3l -once
```

Published in `dtrichards01/private-catalog-eda` as
`ghcr.io/dtrichards01/private-eda-registry/firewall:v1.0.0`.
The UI category is **Firewalls**.
