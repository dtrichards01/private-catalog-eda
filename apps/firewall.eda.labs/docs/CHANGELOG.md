# Changelog

## v1.8.4

- The Firewall Policy Report page reads as a report. The spec is read-only in the UI (the collector rewrites it on every change), and every field has a title and a description
- Source Health shows a green tick for OK, amber for STALE_SOURCE and grey for UNAVAILABLE, with the platform's NPP Synced icon (`CheckCircleLtr`). Generation shows Enabled, Disabled, Blocked and Rejected the same way, and group states, member IN_SCOPE, rule classification and VALIDATED rules get icons too
- Fields are grouped: Overview (firewall, health, generation, message, summary, virtual networks), Policy (rules, groups, derived), Source (vendor, API, scope, export marker, profile, revision). Correlation ID, rejected-at and the snapshot hashes are under Advanced
- Vendor, management mode, export marker, source health and generation list their values. The values stay out of the CRD, so an unexpected value never fails a write
- `scopeKind` is removed: it only repeated what the vendor implies. Install order matters once: the v1.8.4 collector must rewrite the reports before the app is installed, or the Manifest transaction fails with `unknown fields in spec: [spec.scopeKind]`
- Generation is switched on the Firewall (Policy Generation, Enabled or Disabled); the report shows the outcome

## v1.8.3

- Firewall rules must be built to what EDA can tag. Address group names are no longer lowercased: a group maps to the GroupTag of exactly its name, and a name with upper case (Palo Alto `EDA-RED`) is GROUP_NAME_NOT_LOWERCASE. The group derives no GroupTag, and every rule that uses it is rejected (UNSUPPORTED, no candidate)
- A `/32` member, including a DAG registered IP, is rejected with HOST_MEMBER_NOT_SUPPORTED: the fabric tags attachments, not addresses. This replaces PREFIX_MEMBER_NOT_IN_V1, which flagged the opposite case
- A member must equal an IRB or routed-interface subnet. A prefix that only overlaps one is SUBNET_NOT_ATTACHMENT. Every VLAN and bridge interface of the subnet's bridge domain, or its routed interface, must carry the group's GroupTag and no other, else SUBNET_SPLIT_ACROSS_TAGS
- Routed interfaces count: their subnets are members, and an AssociationPolicy on `routedInterfaces` is a checked target instead of blocking the group
- Evaluator `policy-eval/5`, so every report re-correlates
- Lab: the Palo Alto has static groups `eda-red`, `eda-blue` and `eda-green` of the zone `/24`s, used by RED to BLUE and RED to GREEN (`fw-pan-policy-fixtures.sh align`). RED to SECURE keeps the upper-case groups and shows the rejection. The fabric result is unchanged: 3 entries

## v1.8.2

- Advanced Networking has a Default Router field. The spine default interface and BGP peer join that router; empty keeps the node name. A Fabric builds its default routers as `router-<node>`, so FortiGate 2 on a Fabric spine sets `router-srl-spine-1`
- The lab moved to `clab-srl-leaf-spine-dcgw`, on firewall-only VNETs: Palo Alto between `fw-pan-inside` and `fw-pan-outside`, FortiGate 1 between `fw-fg-inside` and `fw-fg-outside`, one client per zone on `e1-31`, FortiGate 2 on `srl-spine-1` and `srl-spine-2` `e1-11`. The DCI and tenancy VNETs are untouched
- The `pan-d3l` lab is destroyed and its namespace removed
- Lab fix, no app change: the firewall VNETs in `dcgw-fw-vnets.yaml` now set EVI, VNI and route targets explicitly (3101 to 3212). Pool allocation had handed them the numbers the DCI VNETs set by hand (EVI 100 to 109, VNI 200 to 209), including the DCI stitch target `target:1:101`. Isolation was re-verified afterwards
- Docs: the Microsegmentation default action is allow. There is no default-action setting, so traffic that matches no entry is forwarded (POLICY-GATES.md)

## v1.8.1

- Firewall Policy Reports open in the UI again. The list had no Name column, so its query did not fetch the name, and View asked the API for `firewallpolicyreports/undefined` and showed an empty `{}`. The default columns now start with name and namespace

## v1.8.0

- The firewall's address groups become GroupTags. Every address group an exported rule names is built as a derived GroupTag, named in lower case (Palo Alto `EDA-RED` is `eda-red`), once the Firewall has Policy Generation Enabled. A GroupTag the operator already made with that name is used instead, and a group name that is not a valid tag name is shown as GROUPTAG_NAME_INVALID
- Where a GroupTag attaches stays with the operator's AssociationPolicies. A derived GroupTag with no AssociationPolicy shows GROUPTAG_NOT_ASSOCIATED, and its rules are shown and not translated until it is associated
- When two firewalls in a namespace have a group of the same name, the first by name derives the GroupTag and the other uses it
- Overlapping membership is checked only between groups whose tags are associated
- The report shows each group's tag source (operator, derived, or another firewall) and the number of derived GroupTags on its status
- `examples/07-microseg-tags.yaml` now holds only the AssociationPolicies

## v1.7.1

- A slow commit is no longer taken for a refusal. The collector marks a report Rejected only when two polls after the 30 second commit wait still do not see the committed status. Live on v1.7.0, the first write after the app install was marked Rejected because the state engine was still loading the new intents; the 15 minute retry then built the policy

## v1.7.0

- Policy is defined on the firewall, learnt in EDA, and translated onto the existing microsegmentation GroupTags. A firewall address group maps to the GroupTag of the same name in lower case (Palo Alto `EDA-RED` is `eda-red`), static or dynamic. A group with no such GroupTag is shown with NO_GROUPTAG and its rules are not translated
- The Firewall app no longer creates GroupTags or AssociationPolicies. Where a GroupTag is attached is read from the operator's AssociationPolicies (VLANs, bridge interfaces, IRB interfaces), and every firewall member must sit in an IRB subnet of those attachments (MEMBER_OUTSIDE_TAG_TARGETS, GROUPTAG_NOT_ASSOCIATED). Selector, routed-interface and static-route associations cannot be checked and block the group (ASSOCIATION_SELECTOR_NOT_EXPANDED)
- One MicroSegmentationPolicy per Firewall, `fw-<firewall>`, is the only derived resource, over the virtual networks where its GroupTags are attached. It coexists with operator policies
- FirewallPolicySource is removed. There is one FirewallPolicyReport per Firewall, named after it, always written: discovery and translation always run, and Firewall `policyGeneration` is the only switch. New Firewall `spec.policyScope` names the vsys or VDOM (default `vsys1` or `root`). A report whose Firewall is deleted is deleted with its policy
- The report state intent writes the committed generation, hash, policy name, entry count and translated rule count to the report's own status, and the report list shows them. The collector reads them to detect a refused transaction
- Live, clab-pan-d3l: operator GroupTags `eda-red`, `eda-blue`, `eda-green` and their AssociationPolicies (`examples/07-microseg-tags.yaml`); `fw-palo-alto` translates eda-red to eda-blue TCP 80 and 443 Accept and eda-red to eda-green Drop. The old app-built red, blue and green objects were removed with the old report

## v1.6.2

- Each derived MicroSegmentationPolicy entry sets `bidirectional` explicitly: true for Accept, so return traffic passes as on the stateful firewall; false for Drop, which the firewall applies one way only. v1.6.1 left it unset, and the Microsegmentation App defaulted every entry to true. That also dropped green to red, which the Palo Alto rule does not
- First live build, 2026-11-01, clab-pan-d3l. The four zone routers were changed from Simple to EVPNVXLAN (`pan-d3l-vnets.yaml`). Simple was a build mistake: on an EVPN fabric every VNET router is EVPNVXLAN, and Policy Generation set to Enabled. GroupTags red, blue and green, three AssociationPolicies and `fwpol-palo-alto-vsys1` were built as derived resources of the report, and both firewall paths still ping

## v1.6.1

- Generation Blocked: the Microsegmentation App puts group-based policy under each VRF's bgp-evpn instance, so every router of a targeted virtual network must be type EVPNVXLAN. A Simple router (all four pan-d3l VRFs) is reported as ROUTER_NOT_EVPN with the router name, and nothing is attempted. The translation stays on the report as a preview
- A refused derive is now detected. A report write is accepted by Kubernetes at once and EDA commits it afterwards, so v1.6.0 never saw the failure (live: two FAILED transactions, then the source stayed Disabled). The collector now checks that the source status shows the Enabled translation within 30 seconds and otherwise rewrites the report as Rejected with DERIVE_REJECTED

## v1.6.0

- Firewall `spec.policyGeneration` Enabled or Disabled, default Disabled. It is the app's switch for auto generation: a derive-mode source builds Microsegmentation App objects only when its Firewall says Enabled. Disabled keeps the translation on the report as a preview, adds POLICY_GENERATION_DISABLED, and removes anything already built. Report and source status carry `generation` (Enabled, Disabled, Rejected); new Generation column
- When EDA refuses the derived objects (for example a VRF without bgp-evpn, which the Microsegmentation App needs), the collector rewrites the report with generation Rejected and DERIVE_REJECTED naming the node path and error, so the report still lands and the fabric is untouched. The same translation is retried after 15 minutes; a changed one at once. v1.5.0 retried a refused transaction on every poll
- Vendor-neutral policy model. Each vendor has a profile: management API, scope kind (Palo Alto vsys, FortiGate VDOM, default vsys1 or root), export marker (Palo Alto rule tag, FortiGate policy section label `global-label` named `eda-export-to-gbp`) and group identity (Palo Alto dynamic address group with a one-tag filter, FortiGate address group). Rules carry a section label, and `accept` is an allow action. Everything after normalisation is shared. The FortiGate reader is not in this release, so a FortiGate source reports UNAVAILABLE with VENDOR_READER_NOT_IMPLEMENTED. Source scope accepts VDOM names, `tag` is optional (Palo Alto only), and the report and source status show vendor, scopeKind and exportMarker

## v1.5.0

- FirewallPolicySource mode `derive`. Setting it is the one approval: the Palo Alto rules then become Microsegmentation App objects and follow every PAN commit. The collector translates, under the built-in profile `microseg-1to1/1`, each enabled rule tagged `eda-export-to-gbp` whose source and destination are one bound address group each, IPv4, service any or TCP/UDP destination port or range (plus source port), allow or deny. One MicroSegmentationPolicy entry per protocol and port, in PAN rule order. Applications, users, URL, zones, negation, profiles and anything else stay NGFW_REQUIRED or UNSUPPORTED and are never translated
- New config intent on FirewallPolicyReport. In derive mode it emits a GroupTag per used binding (skipped if an operator already made one), an AssociationPolicy `fwpol-<source>-<grouptag>` on the binding's VLANs or bridge interfaces, and one MicroSegmentationPolicy `fwpol-<source>` over the source's virtual networks. They are derived resources of the report, read-only in the UI, labelled `firewall.eda.labs/policy-source`. Observe mode emits none, so going back to observe removes them
- Group bindings name their targets (`vlans`, `bridgeInterfaces`). Every member IP must sit in a subnet of a target's bridge domain (MEMBER_OUTSIDE_TARGETS), targets must exist in scope (TARGET_NOT_FOUND, TARGET_OUT_OF_SCOPE), and two bindings on one target are both flagged TARGET_SHARED. A port of 0 is not translated, since it would widen the entry to every port
- `additionalVirtualNetworks`: members may sit in further VNETs. With more than one VNET the derived GroupTags are Global
- Source status shows the mode, the profile, the derived policy, entry count, GroupTags, AssociationPolicies and hash, and per rule the translation state and entry count. New Mode and Derived columns. Firewall Policy Reports appear under Firewalls in the UI

## v1.4.1 (collector only)

- Collector: Palo Alto interfaces are read with `show interface all` instead of `show interface hardware`. The hardware view has no address or zone, so observed address and zone were always empty on the Palo Alto and the v1.4.0 config state stayed Pending. The port state from the hw entry and the running address and zone from the logical interface are merged by name. A VLAN NIC is read back on its subinterface

## v1.4.0

- New kinds FirewallPolicySource (config) and FirewallPolicyReport (status, written by the collector). A source names a firewall, a PAN vsys, an EDA virtual network and service target, and the PAN address group, tag and EDA GroupTag bindings. The collector reads the PAN security rules, objects, DAG membership and registered IPs through the XML API, read-only, and classifies each rule as FABRIC_ENFORCEABLE, FABRIC_ENFORCEABLE_DENY, NGFW_REQUIRED or UNSUPPORTED per test plan v0.18 section 18. Only enabled rules tagged exactly `eda-export-to-gbp` are eligible. No compatibility profile ships, so fabric candidates report UNSUPPORTED with COMPATIBILITY_UNVALIDATED and the candidate class. Nothing is written to the fabric or the firewall
- Policy reads are checked against the PAN config audit version before and after the read. A change during the read reports STALE_SOURCE, and an unreadable firewall keeps the last good result with source health UNAVAILABLE
- FirewallInterface status: `configState` says whether the firewall runs the spec, read back through the vendor API after each push. Address, zone, the BGP peer and VXLAN services are compared with the running state: NotManaged, Pending, Committing (a Palo Alto commit job is queued or running), Applied, Verified (Applied and Up), Failed (apply error or a failed commit job, with its detail), Removing. `configDetail` lists what is missing, `pendingSince` restarts on each new `metadata.generation`, and a change not applied within 10 minutes says so. Status only, no alarm. New Config column
- Collector: a Palo Alto API error no longer includes the request URL, which carried the password or API key

## v1.3.13 (collector only)

- Collector: no heartbeat. A FirewallReport is written only when it changes, so an idle firewall creates no EDA transactions. `lastChecked` is the time of the last change, not the last poll. Collector liveness is the `eda-fwstatus` pod and its `polling firewalls` log line

## v1.3.12 (collector only)

- Collector: a new informational or debug event no longer writes the FirewallReport on its own. The firewalls log lines such as "DHCP statistics" and "Connection to Update server closed" every minute or two, so v1.3.11 still wrote a report about every 80 seconds. The events list is refreshed with the next other change or the 10-minute heartbeat. A new event at notice, warning, or above (FortiGate) or low and above (Palo Alto) is still written on the poll that sees it

## v1.3.11 (collector only)

- Collector: a FirewallReport is written only when it changes, or every 10 minutes so `lastChecked` still shows the collector is alive. Every report write is an EDA transaction, and v1.3.10 wrote all three lab reports every 30 seconds. Health, operational state, NIC state, BGP and message changes are still written on the poll that sees them
- Collector: events leave out the collector's own admin logins and logouts (FortiGate `action` login/logout, Palo Alto `auth-success` and "User ... logged in via") for the API user in the Firewall secret, and the FortiGate performance statistics row. They changed on every poll. Logins by other users are kept. Up to 50 log rows are read so five real events remain
- Collector: Palo Alto events show the log description (`opaque`) instead of the event ID, for example "Port ethernet1/2: Down" instead of `link-change`
- Collector: report interfaces are sorted by name. v1.3.10 listed them in random order

## v1.3.10

- Firewall Interface UI: Attachment and BGP are hidden while Advanced Networking is set, and Advanced Networking is hidden while either is set. Saving with both is refused. EDA can hide a field but not grey it out. The descriptions say that Advanced Networking creates the spine default interface, default BGP group and peer, and policy, and that Attachment and BGP need the virtual network created first
- Collector: no Palo Alto commit is queued while another commit waits. A commit takes about 3 minutes on the lab VM-50, and v1.3.9 queued one every poll, so 20 commits waited and the new addresses never reached the running config. A candidate left by an earlier failed commit is committed on the next poll, and a commit error carries the API detail
- Collector: when an interface address or fabric peer changes, the old Palo Alto address and the peer keyed by the old gateway, and the old FortiGate neighbor, are removed. v1.3.9 left the old `/24` on the Palo Alto port next to the new `/30`

## v1.3.9

- Firewall Interface `bgp.peerIP` (Fabric Peer IP). The fabric address the firewall peers with; it must be in the interface subnet and not the firewall address
- Without it, the collector derives the peer from the prefix: the other host on a `/30` or `/31`, and `.254` (or `.253`) in larger subnets. v1.3.8 always used `.254`, so a `/30` routed link pushed a neighbor that was not on the link

## Unreleased (lab only)

- `pan-d3l-vnets.yaml`: each firewall VNET router selects its own leaf through the TopoNode label `firewall-zone` (`inside` on leaf1, `outside` on leaf2) instead of `role=leaf`. The spare VRF and IRB on the other leaf were oper-down and held all four VNETs at Degraded. They are Up on one node each

## v1.3.8

- Collector: when the loopback VTEP cannot be created, that VDOM's VXLAN services are left untouched. v1.3.7 moved `vxlan200` and `vxlan201` onto the missing loopback, deleting them, when the FortiGate 2 evaluation license refused the loopback (CMDB -4, maximum number of entries)
- Example 06 no longer sets `vtepAddress`
- Docs: FortiGate 2 VXLAN root cause. SR Linux does not accept a route whose prefix contains its own next hop, so each spine accepts only the other FortiGate link subnet, and VXLAN reaches FortiGate 2 on `port3`. A loopback VTEP on a licensed FortiGate 2, or each spine advertising its own link subnet, fixes it. Palo Alto interfaces pushed and Up

## v1.3.7

- Firewall Interface `advanced.vtepAddress` (VTEP Address, IPv4 `/32`). This turns on the loopback VTEP the collector gained in v1.3.5
- Collector polls every 30 seconds instead of 60 (`-interval 30s` in `deploy/collector.yaml`)

## v1.3.6

- Docs only: FortiGate 1 untagged leaf cable, the FortiGate 2 loopback VTEP, the missing-status OpenAPI failure, and the Palo Alto interfaces recreated observe only. The collector is rebuilt from the same code under a new tag

## v1.3.5

- Firewall Inventory has a `status` object. Without it, EDA could not generate the app OpenAPI (`did not find status ... kind FirewallInventory`), `GET /openapi/v3/apps/firewall.eda.labs/v1alpha1` returned 500, and the Firewalls category vanished from the UI in v1.3.3
- Collector: an Advanced Networking interface with a VTEP address gets FortiGate loopback `eda-vtep` (`/32`, ping) in its VDOM. Its VXLAN services are sourced from that loopback, and the `/32` is advertised in BGP instead of the link subnet. Removing the VTEP deletes the loopback. The Firewall Interface field `advanced.vtepAddress` is not in the schema yet, so this is inactive
- Firewall Interface intent rejects a VTEP address that is not an IPv4 `/32`, or that is set without `ipv4-unicast`

## v1.3.4 (collector only)

- FortiGate interface zone is read from the `zone` field only. Role (`lan`) is not a zone, and comparing it against the spec zone marked interfaces Degraded

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
