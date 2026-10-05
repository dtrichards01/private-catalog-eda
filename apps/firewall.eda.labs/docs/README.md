# Firewalls

External firewall endpoints for the `pan-d3l` lab. Palo Alto and FortiGate are
not TopoNodes. Each firewall is a `Firewall` resource. Each NIC is a
`FirewallInterface`. Palo Alto and Fortinet-1 fabric objects, the edge
port, the router, and the BGP peer, are part of the virtual network.
The app pushes the NIC and its BGP session to the firewall API. The firewall
Vendor selects Palo Alto or FortiGate, and Tenant selects the virtual system
or VDOM. Deleting the interface removes that NIC config and BGP neighbor
from the firewall.
Advanced Networking on Fortinet-2 emits the default interface, EVPN policy,
default BGP group, and default BGP peer. It does not emit a default router.

| Endpoint | Role | Management | Data |
|----------|------|------------|------|
| `palo-alto` | Leaf eBGP, one virtual system | `https://100.124.186.51:8444` | `ethernet1/1` `10.31.1.1/24` on `pan-inside`, `ethernet1/2` `10.31.2.1/24` on `pan-outside` |
| `fortigate` | Leaf PE/CE. One VLAN and one eBGP session per VDOM | `https://100.124.186.50:8443` | `port2` toward leaf1, `port3` toward leaf2. Live addresses `10.21.0.1/24` and `10.22.0.1/24` are still untagged in VDOM `root` |
| `fortigate-2` | EVPN. Fabric underlay from the spines | `https://100.124.186.50:8445` | `port2` to spine1, `port3` to spine2. Both are up at `0.0.0.0` |

`spec.fabric` is a dropdown of the fabrics in the namespace.

Each interface sets `spec.tenant`. Palo Alto uses a virtual system (`vsys1`).
FortiGate uses a VDOM. Both FortiGates are in `multi-vdom` mode. The license
on each allows two VDOMs (`used` 1, `max` 2). Only `root` exists. Creating
`service` returned CMDB error -4, maximum number of entries, so VDOM 2 is
not on the box yet.

Each tenant has one route handoff. `clients-use-firewall` is the lab default:
clients gateway to the firewall and no default route is advertised.
`firewall-originates-default` tells the firewall BGP session to advertise
`0.0.0.0/0`. `fabric-static-to-firewall` is the fabric static toward the
firewall address. Only one of those is selected.

Palo Alto tenants use eBGP to a virtual network. The fabric gateway on each
network is `.254`.

The two FortiGates are not the same role.

FortiGate 1 is standard leaf connectivity. Each tenant is a VDOM. Each VDOM
gets its own VLAN (`encapType: dot1q` plus `vlanID`) and its own eBGP PE/CE
session to the leaf. It does not join the fabric underlay and it does not
originate the EVPN VTEP. The cables in the lab today are still untagged
iBGP in VDOM `root` on leaf `e1-5` (VXLAN VNI 10021 and 10022). That cutover
waits until VDOM 2 exists.

FortiGate 2 is the EVPN firewall. The fabric underlay extends into it on
interlinks to the spines: spine1 `e1-3` to `port2` (VXLAN VNI 10023) and
spine2 `e1-3` to `port3` (VXLAN VNI 10024). Those are not leaf edge ports
and they are not client gateways. iBGP to the spine route reflectors and
the VTEP belong on this firewall. The cluster still has the earlier leaf
`e1-7` / `e1-8` cables and VNETs `fg2-inside` / `fg2-outside`. The repo
files `start-fw-vms.sh` and `pan-d3l-fg2.yaml` name the spine ports and
have not been applied.

Palo Alto leaves Advanced Networking empty. A FortiGate EVPN VDOM uses
**Advanced Networking** (`underlay: evpn-vxlan`). On FortiGate 1 the leaf
cable is `dot1q`. On FortiGate 2 the spine links carry the underlay, not a
client VLAN.

Credentials stay in Secrets (`username`, `password`). Examples use `replace-me`.

Firewall communication is the vendor API only. Palo Alto uses the XML API
(`/api/`). FortiGate uses the REST API (`/api/v2`). There is no firewall CLI
or SSH session. These firewalls do not stream gNMI.

## What the UI shows

The Firewalls page reads the state database, not `kubectl`. The collector
(`fwstatus`) polls the vendor API and writes a `FirewallReport`. The report
state script copies that onto the Firewall and each FirewallInterface:

```python
eda.update_cr(
    schema=eda.Schema(group="firewall.eda.labs", version="v1alpha1", kind="Firewall"),
    name=name,
    status={...},
)
```

`eda.Schema` is required. The Firewall and FirewallInterface state scripts
do not publish a hardcoded `Up`. Every kind in the app, including
`FirewallReport`, needs a `status` object in its OpenAPI schema. Without
that, `GET /openapi/v3/apps/firewall.eda.labs/v1alpha1` returns 500 and the
Firewalls page lists nothing. The report spec must name every field the
collector writes (`health`, `bgp`, `events`, `interfaces`, and the rest).
`x-kubernetes-preserve-unknown-fields` does not satisfy the state controller.

`kubectl` status and `fwstatus` with `FWSTATUS_STATE_DB=1` write a different
store. They do not fill the page. Do not run that publisher from `eda-toolbox`.

The State Engine cannot call the firewall HTTPS API. The collector does.
It runs as Deployment `eda-fwstatus` in `eda-system`. Installing the app
does not start that Deployment. `spec.configureFirewall` on an interface
is what allows the collector to push that NIC through the vendor API.
Leave it off to only create the Nokia leaf attachment. The collector does
not rewrite BGP when it starts, and it does not originate a default route.

## States

The page field `status.operationalState` is this app's rollup, not a vendor
enum. `fwstatus` computes it from the API:

| Rollup | Health | When |
|--------|--------|------|
| `Up` | 100 | API login succeeded and every configured NIC is up |
| `Degraded` | 70 | API ok, and at least one NIC is down |
| `Degraded` | 40 | API login failed |
| `Degraded` | 50 | The API was attempted without credentials |
| `Down` | 0 | API unreachable |
| `Unknown` | 0 | No credentials, or the NIC was missing from the API response |

A NIC `operationalState` is `Up`, `Down`, `Degraded`, or `Unknown`. The port
state comes from the vendor API. When that FirewallInterface has BGP, `Up`
also requires the neighbor in that NIC subnet to be `Established`. A port
that is up with the session down is `Degraded`. An interface without BGP
stays on the port state. The list shows the same circle icon as other EDA
resources: `ArrowUpCircle` for Up, `AlarmCircle` for Degraded,
`ArrowDownCircle` for Down, and `RemoveCircle` for Unknown.

FortiGate interface state is CMDB `system/interface` field `status`: `up` or
`down`. Palo Alto interface state is the operational XML `state` or
`status`: `up` or `down`.

BGP remains a separate list, `status.bgp[].state`, with the session string
from the API. That list does not replace the NIC rollup above. Palo Alto is
`show routing protocol bgp peer` `<status>`. FortiGate is
`/api/v2/monitor/router/bgp/neighbors` field `state`. Both return the BGP
state name. `Established` is the up session. The other names those APIs
return are `Idle`, `Connect`, `Active`, `OpenSent`, and `OpenConfirm`.

Published in `dtrichards01/private-catalog-eda` as
`ghcr.io/dtrichards01/private-eda-registry/firewall:v1.2.4`.
The collector image is `ghcr.io/dtrichards01/private-eda-registry/fwstatus:v1.2.4`.
The UI category is **Firewalls**. There is no Bridge field. Node and
Interface on an attachment are pickers: the interface list is the
interfaces of the selected node.

The 2026-10-04 demo on Talos #2 uses `clients-use-firewall`. Palo Alto
tenant `vsys1` is eBGP. The running FortiGate 1 sessions are still iBGP in
VDOM `root`, with Advanced Networking VNI 200 inside and 201 outside.
That is the live path, not the leaf PE/CE VLAN target above. Both
FortiGates are `multi-vdom`, and only `root` is present. Client1 to
client2 and client3 to client4 pinged with no loss after multi-vdom was
turned on. FortiGate 2 has a valid evaluation license and no data-port
addresses. Do not add a default route.
