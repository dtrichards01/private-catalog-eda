# Firewall prototype

This is a concept prototype, not a product. The feature set is limited and
covers two lab use cases on Talos EDA #2, namespace `clab-pan-d3l`.

For production, the interface between EDA and the firewall API will be the
Push Pull Provider in EDA 26.12.1. The collector in this prototype
(`fwstatus`) is a lab stand-in for that interface.

Operational detail and the same topology diagram are also in
[README.md](README.md).

## Use case 1 — General firewall

An external firewall attaches to edge interfaces. Palo Alto and FortiGate 1
are this shape.

The virtual network owns the fabric service: the edge port, the router, the
routed or IRB interface, and the eBGP peer. This app does not create that
virtual network and does not emit those objects. Build the virtual network
first. The Virtual Network field lists virtual networks that already exist.

A Firewall with no Firewall Interface is monitoring only. A Firewall
Interface pushes the NIC when Configure Firewall is set, and pushes eBGP
when BGP mode is `ebgp`. Vendor on the Firewall selects Palo Alto or
FortiGate. Tenant selects the virtual system or VDOM. Empty uses `vsys1` or
`root`.

The firewall API write is address, VLAN, zone, optional ping, and the eBGP
neighbor. Fabric AS is the peer AS. Firewall AS is the firewall local AS.
The app does not originate a default route. Deleting the Firewall Interface
removes the config the collector has recorded. The physical port stays.

## Use case 2 — FortiGate on the spine underlay

FortiGate 2 attaches to the spines, not to leaf edge ports. Client virtual
networks stay on the leaves. Advanced Networking emits the default
interface, EVPN policy, default BGP group, and default BGP peer. It does
not emit a default router or the spine interface. BGP on the firewall is
eBGP, plus EVPN only when Advanced Networking is set.

## Topology

```mermaid
flowchart LR
  subgraph spines [Spines]
    spine1
    spine2
  end
  subgraph leaves [Leaves]
    leaf1
    leaf2
  end
  spine1 ---|e1-1 / e1-1| leaf1
  spine2 ---|e1-1 / e1-2| leaf1
  spine1 ---|e1-2 / e1-1| leaf2
  spine2 ---|e1-2 / e1-2| leaf2
  client1 ---|eth1 / e1-3| leaf1
  client3 ---|eth1 / e1-6| leaf1
  client2 ---|eth1 / e1-3| leaf2
  client4 ---|eth1 / e1-6| leaf2
  leaf1 ---|e1-4 / ethernet1/1| palo[Palo Alto]
  leaf2 ---|e1-4 / ethernet1/2| palo
  leaf1 ---|e1-5 VXLAN 10021 / port2| fg1[FortiGate 1]
  leaf2 ---|e1-5 VXLAN 10022 / port3| fg1
  spine1 ---|e1-3 VXLAN 10023 / port2| fg2[FortiGate 2]
  spine2 ---|e1-3 VXLAN 10024 / port3| fg2
```

Use case 1 is Palo Alto (`ethernet1/1`, `ethernet1/2`) and FortiGate 1
(`port2`, `port3` on the leaves). Use case 2 is FortiGate 2 (`port2`,
`port3` on the spines).

## Resources and intents

Three resources:

| Resource | Role |
|----------|------|
| Firewall | One external firewall. Vendor is `paloalto` or `fortinet`. Management is the API URL and the credential Secret. A Firewall alone is monitoring only. |
| Firewall Interface | One NIC. Configure Firewall pushes the address. BGP mode `ebgp` pushes the neighbor. Advanced Networking is use case 2 only. |
| Firewall Report | What the collector last read and wrote. The UI does not read this object directly. |

Five intents. The state scripts on Firewall and Firewall Interface do nothing, so they cannot overwrite the collector with a hardcoded Up.

| Intent | Role |
|--------|------|
| Firewall config | Checks the Firewall. It does not create a virtual network, router, or BGP peer. |
| Firewall state | No-op. Status comes from the report. |
| Firewall Interface config | Checks the interface. Use case 1 emits nothing on the fabric. Use case 2 emits the default interface, EVPN policy, default BGP group, and default BGP peer. |
| Firewall Interface state | No-op. Status comes from the report. |
| Firewall Report state | Copies the collector report onto the Firewall and each Firewall Interface. That is what the Firewalls page reads. |

## Collector and the two APIs

`fwstatus` runs as Deployment `eda-fwstatus` in `eda-system`. Installing the app does not start it. It polls about once a minute. The State Engine cannot call the firewall.

Each poll, for each Firewall:

1. Read the vendor, the API URL, and the Secret (`username`, `password`).
2. Split Firewall Interfaces into live and deleting.
3. Withdraw NICs recorded on a previous push and no longer live. Remove the finalizer after that succeeds.
4. Push live NICs that have Configure Firewall set.
5. Push eBGP when mode is `ebgp` and both AS numbers, the address, and the NIC name are set.
6. Read health, interface state, and BGP state back from the API.
7. Write a Firewall Report. The report state intent publishes that onto the UI.

The Firewall `spec.vendor` selects the API. Tenant selects where the push goes. Empty tenant is Palo Alto `vsys1` or FortiGate `root`.

Palo Alto uses the XML API (`/api/`). The collector logs in with a key, sets candidate config, and commits. Untagged address is a layer3 IP entry on the physical port. A VLAN is a subinterface (`ethernet1/1.21`). Allow Ping creates profile `eda-ping` and attaches it. BGP uses the `default` virtual router: Firewall AS is `local-as`, Fabric AS is the peer AS, and the peer address is the fabric gateway (`.254`). `vsys1` uses the device virtual-router path. Another vsys uses that vsys path. This lab only has `vsys1`.

FortiGate uses the REST API (`/api/v2`). The collector logs in and sends CMDB calls with `?vdom=` set to the tenant. A VLAN is a separate interface (`port2.21`) on the parent port. Allow Ping adds `ping` to `allowaccess`. BGP is a small update of AS and router-id, then a neighbor whose IP is the fabric gateway, whose remote AS is the Fabric AS, and whose interface is the port or VLAN interface. `activate-evpn` is set only for use case 2. The collector does not originate a default route on either vendor.

A delete removes only a NIC the collector has recorded, on the next poll. The physical port stays. Palo Alto drops the address, zone member, BGP peer, VLAN unit, and `eda-ping` when nothing else uses it. FortiGate deletes the neighbor and the VLAN interface, or clears the address on an untagged port. `port1` is never cleared.

## Limited feature set

- Palo Alto XML API and FortiGate REST API only. No CLI, SSH, or gNMI.
- No virtual network, VDOM, or virtual system is created. A second FortiGate
  VDOM and a second Palo Alto virtual system have to exist before a push.
- Tenant is free text. There is no VDOM or vsys dropdown.
- Allow Ping is off unless set. On Palo Alto that attaches management
  profile `eda-ping`. When it is off, ping does not work.
- VLAN is optional. Empty leaves the port untagged.
- The collector removes a NIC only after it has recorded the push.
- Gateway addressing is `.254` in the NIC subnet (`.253` when the firewall
  itself is `.254`).
