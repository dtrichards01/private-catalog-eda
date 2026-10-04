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

`spec.fabric` is a dropdown of the fabrics in the namespace.

Each interface sets `spec.tenant`. Palo Alto uses a virtual system (`vsys1`).
FortiGate uses a VDOM (`root`, and `service` when the second VDOM is on).
The license allows two VDOMs.

Each tenant has one route handoff. `clients-use-firewall` is the lab default:
clients gateway to the firewall and no default route is advertised.
`firewall-originates-default` tells the firewall BGP session to advertise
`0.0.0.0/0`. `fabric-static-to-firewall` is the fabric static toward the
firewall address. Only one of those is selected.

Palo Alto tenants use eBGP to a virtual network. The fabric gateway on each
network is `.254`. A FortiGate edge VDOM can use VLAN eBGP to the leaf
(`encapType: dot1q` plus `vlanID`). A FortiGate service VDOM uses iBGP and
**Advanced Networking** (`underlay: evpn-vxlan`, bridge-domain VNI 200 inside
and 201 outside). Palo Alto leaves Advanced Networking empty. The leaf cable
stays untagged when the VNI is set; VXLAN is the bridge domain.

Credentials stay in Secrets (`username`, `password`). Examples use `replace-me`.

Firewall communication is the vendor API only. Palo Alto uses the XML API
(`/api/`). FortiGate uses the REST API (`/api/v2`). `fwstatus` reads health, version, serial, license, interface state, BGP, and
recent vendor events from those APIs. These firewalls do not stream gNMI.
Each poll writes `.status`, and that write is what EDA shows. It pushes a
NIC address, ping, admin state, zone, or BGP session only when the API state
differs, and it does not originate a default route.
There is no firewall CLI or SSH session.

`fwstatus` uses the EDA SDK (`eda.dev/edk`) Kubernetes client to write
`.status` (health, version, serial, license, and the networking rollup).
Inside the cluster, `FWSTATUS_STATE_DB=1` also publishes that status to the
state aggregator. Do not set that flag outside the cluster.

```bash
go run ./cmd/fwstatus -namespace clab-pan-d3l -once
```

Published in `dtrichards01/private-catalog-eda` as
`ghcr.io/dtrichards01/private-eda-registry/firewall:v1.1.0`.
The UI category is **Firewalls**.

The 2026-10-04 demo on Talos #2 uses `clients-use-firewall`. Palo Alto
tenant `vsys1` is eBGP. FortiGate tenant `root` is iBGP, with Advanced
Networking VNI 200 inside and 201 outside. The second tenant `service` is
named on the firewall and has no NIC. Multi-vdom is off. Both firewalls
were Up with health 100, the four BGP peers were Up, and client1 to
client2 and client3 to client4 pinged with no loss.
