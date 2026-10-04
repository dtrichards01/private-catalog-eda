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
(`/api/`). FortiGate uses the REST API (`/api/v2`). There is no firewall CLI
or SSH session. These firewalls do not stream gNMI.

## What the UI shows

The Firewalls page reads the state database, not `kubectl`. The State Engine
runs `firewall/intents/firewall/state_intent.py` when the Firewall object
changes. That script must call:

```python
eda.update_cr(
    schema=eda.Schema(group="firewall.eda.labs", version="v1alpha1", kind="Firewall"),
    name=name,
    status={...},
)
```

`eda.Schema` is required. A missing schema raises `TypeError`, and the
v1.1.0 script swallowed that error, so the page stayed blank. The same
call on `FirewallInterface` fills the interface Operational State column.

`kubectl` status and `fwstatus` with `FWSTATUS_STATE_DB=1` write a different
store. They do not fill the page. Do not run that publisher from `eda-toolbox`.

The State Engine runs the script when the object is created or changed. It
does not call the firewall HTTPS API on a timer. The script runs in
MicroPython and cannot import SSL. The 2026-10-04 lab script publishes the
last API result onto the object: both firewalls `Up`, health `100`, and each
interface `Up`. A later vendor poll has to call this same `update_cr` or the
page stays on that result.

`fwstatus -poll-only` still reads the vendor API and writes Kubernetes
status. It pushes a NIC address, ping, admin state, zone, or BGP session
only when the API state differs, and it does not originate a default route.

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

A NIC `operationalState` is `Up`, `Down`, or `Unknown`. Any other interface
string from the API is kept as-is.

FortiGate interface state is CMDB `system/interface` field `status`: `up` or
`down`. Palo Alto interface state is the operational XML `state` or
`status`: `up` or `down`.

BGP is a separate list, `status.bgp[].state`. It is the session string from
the API, not folded into `Up` or `Down`. Palo Alto is
`show routing protocol bgp peer` `<status>`. FortiGate is
`/api/v2/monitor/router/bgp/neighbors` field `state`. Both return the BGP
state name. `Established` is the up session. The other names those APIs
return are `Idle`, `Connect`, `Active`, `OpenSent`, and `OpenConfirm`.

Published in `dtrichards01/private-catalog-eda` as
`ghcr.io/dtrichards01/private-eda-registry/firewall:v1.1.0`.
The UI category is **Firewalls**.

The 2026-10-04 demo on Talos #2 uses `clients-use-firewall`. Palo Alto
tenant `vsys1` is eBGP. FortiGate tenant `root` is iBGP, with Advanced
Networking VNI 200 inside and 201 outside. The second tenant `service` is
named on the firewall and has no NIC. Multi-vdom is off. Both firewalls
were Up with health 100, the four BGP peers were Up, and client1 to
client2 and client3 to client4 pinged with no loss.
