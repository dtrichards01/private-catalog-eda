# Changelog

## Lab, 2026-10-04

The installed image is still v1.1.0. The Firewalls page was blank because
the state script did not call `eda.update_cr` with `eda.Schema`. The live
scripts on the in-cluster app git (`e41b5bc`) publish `Up` / health 100 and
interface `Up`. Reinstalling the v1.1.0 image replaces that git commit.
`kubectl` status is not the page.

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
