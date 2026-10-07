# Changelog

## v1.3.3

- Firewall status `healthReason`: each interface that is not up and its cause (for example `port2: BGP 10.21.0.254 Active`), or the API error. Shown as the Health Reason column
- Health shows its meaning from the States table (`80 · interface degraded`, `70 · interface down`, and so on). EDA has no list-cell tooltip
- BGP detail on an interface names the neighbor
- Topology docs: Palo Alto runs on `.51`, both FortiGates on `.50`. VXLAN 10021 to 10024 are host tunnels for the cables, not EVPN VNIs. FortiGate 2 section rewritten around eBGP `evpn` from the spines and the VNI owned by the EDA virtual network. EQL queries for firewall status

## v1.3.1 (collector v1.3.2)

- New kind Firewall Inventory: one row per firewall port or tenant, written by the collector. The Firewall Interface name, Tenant, and service Tenant autocomplete from it once Firewall is set
- Node Interface autocomplete uses an EQL `query` on `.namespace.node.srl.interface`. The previous `eql` template was sent to EDA unexpanded
- Intent runtime passes `eda.Schema` to `eda.update_cr`. Advanced Networking spine objects were not emitted before this
- FortiGate BGP session mode comes from the local and remote AS instead of always `ibgp`
- Collector v1.3.2: the report write no longer panics on integer service fields (VNI, EVI). v1.3.0 and v1.3.1 stopped after the first firewall once FortiGate 2 had services
- Collector needs `firewallinventories` get, list, create, delete

## v1.3.0

- Firewall is vendor, fabric, and management only. `spec.peering` is removed; BGP and tenants are on the Firewall Interface
- Firewall status lists tenants read from the firewall (Palo Alto vsys, FortiGate VDOM)
- Firewall Interface: Firewall is a dropdown, Address is required, Allow Ping covers both vendors
- Configure Firewall off is observe only. The collector no longer pushes BGP for those interfaces
- Classic BGP is eBGP only. Advanced Networking has its own spine node, interface, encapsulation, VLAN, BGP, and address families (`ipv4-unicast`, `evpn`)
- Advanced Networking services: tenant plus client virtual network. The collector reads VNI, EVI, and route target from the bridge domain and pushes the FortiGate EVPN instance, VXLAN interface, and address. A service removed from the list is withdrawn
- With `ipv4-unicast`, the FortiGate advertises the underlay subnet so the leaves reach its VTEP
- Collector needs read access to `bridgedomains.services.eda.nokia.com`

## v1.2.10

- Summary explains each resource and intent, and how the collector uses the Palo Alto XML API and the FortiGate REST API

## v1.2.9

- Summary in `firewall/docs/SUMMARY.md`: concept prototype, two use cases, and the production path (Push Pull Provider in EDA 26.12.1)

## v1.2.8

- Allow Ping is off unless set. Palo Alto attaches management profile `eda-ping` only when it is set, and removes that profile when it is off so the NIC does not answer ping

## v1.2.7

- Palo Alto writes the NIC address as a layer3 IP entry, so the BGP local AS and peer AS can commit
- Allow Ping says it creates management profile `eda-ping`. Fabric AS and Firewall AS name which number is written on the firewall
- Virtual Network lists virtual networks that already exist and does not create one

## v1.2.6

- `firewall/docs/README.md` is the lab writeup and now includes the topology diagram, the VLAN push, and the delete behavior

## v1.2.5

- Firewall Interface has a VLAN field on the main form. Palo Alto pushes it as a subinterface. FortiGate pushes it as a VLAN interface on that port. Empty stays untagged
- Deleting a Firewall Interface also removes the eda-ping management profile from Palo Alto when nothing else uses it

## v1.2.4

- BGP on a FirewallInterface is written to the firewall API. The firewall Vendor selects Palo Alto or FortiGate. Tenant selects the virtual system or VDOM, and empty uses vsys1 or root
- FortiGate eBGP is a neighbor in that VDOM. EVPN is set only when Advanced Networking is on. No default route is originated
- Deleting a FirewallInterface removes that NIC address, zone, and BGP neighbor from the firewall. The collector does this on its next poll

## v1.2.3

- Palo Alto and Fortinet-1 no longer emit a router, IRB, BGP peer, or edge interface. Those belong on the virtual network
- BGP on a FirewallInterface is the firewall-side request. Tenant selects the existing virtual system or VDOM for the API push. Empty uses vsys1 or root
- Advanced Networking still emits the default interface, EVPN policy, default BGP group, and default BGP peer. It does not emit the spine interface or a default router
- Collector image `fwstatus:v1.2.3`

## v1.2.2

- Firewall and FirewallInterface operational state includes BGP when the interface specifies it. A port that is up with that session down is Degraded
- The state column uses the EDA circle icon: Up, Degraded, Down, Unknown
- Advanced Networking on a FirewallInterface emits a default interface, an EVPN policy, a default BGP group, and a default BGP peer. It does not emit a default router and it does not put the spine port in the client virtual network
- The advanced VNI has to match that client virtual network. Edge and underlay sessions are eBGP
- Collector image `fwstatus:v1.2.2` computes that rollup. The app install does not start the collector

## Lab 2026-10-04

Not an app release. FortiGate 1 is the leaf PE/CE firewall: one VLAN and one eBGP session per VDOM. FortiGate 2 is the EVPN firewall: spine1 `e1-3` and spine2 `e1-3` are the underlay interlinks. Both boxes are `multi-vdom`. Only VDOM `root` exists. The live FortiGate 1 cables are still untagged iBGP, and the live FortiGate 2 cables are still the leaf `e1-7` / `e1-8` pair.

## v1.2.1

- FirewallReport declares status and the collector fields, so the Firewalls page loads
- v1.2.0 returned HTTP 500 for the app OpenAPI (`did not find status` on FirewallReport) and the page listed no firewalls

## v1.2.0

- The Bridge field is removed from Firewall Interfaces
- Node and Interface are pickers. The interface list follows the selected node
- Configure Firewall pushes that NIC through the Palo Alto or FortiGate API
- The collector writes a FirewallReport. That report's state script publishes Firewall and FirewallInterface status
- The Firewall and FirewallInterface state scripts no longer publish a hardcoded Up

## v1.1.0

- Each interface names a tenant: a FortiGate VDOM or a Palo Alto virtual system
- Route handoff is clients-use-firewall, firewall-originates-default, or fabric-static-to-firewall
- Advanced Networking holds Fortinet EVPN VXLAN and the VNI. Palo Alto leaves it empty
- A VLAN id is required when the leaf encapsulation is dot1q
- The default route stays off unless the handoff says the firewall originates it

## v1.0.2

- Fabric is a list of the fabrics in the namespace
- Palo Alto tenants use eBGP to a virtual network
- FortiGate joins the underlay with EVPN VXLAN. Each VDOM uses iBGP. The license allows two
- Poll writes health, BGP, and recent events onto the firewall status
- FortiGate VXLAN is the bridge domain. The leaf cable stays untagged

## v1.0.1

- Firewall interfaces commit even when the leaf attachment cannot be emitted
- List columns for the firewall and its NICs

## v1.0.0

- External firewall endpoints for Palo Alto and FortiGate
- Health, status, and interface changes use the vendor API
- Intents validate the CR directly. They do not import generated `pysrc` modules.
