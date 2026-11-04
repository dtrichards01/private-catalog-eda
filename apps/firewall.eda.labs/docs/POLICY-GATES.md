# Firewall policy to EDA microsegmentation

Companion to test plan v0.18 and readiness checklist v0.21. This page says
what the lab app does today, how a Palo Alto rule becomes an EDA
microsegmentation policy, and the lab evidence for each checklist gate.
Status values are the checklist's own. Only the gate owners can record PASS,
so evidenced gates are marked "lab evidence" and stay OPEN on the checklist.

## What runs today (v1.8.3)

Policy is defined on the firewall, learnt in EDA, and built in the
Microsegmentation app as derived resources: the firewall's address groups
become GroupTags and its rules one MicroSegmentationPolicy. Where a GroupTag
attaches stays with the operator's AssociationPolicies, and operators can
keep writing their own GroupTags and MicroSegmentationPolicies next to the
firewall's.

1. For every Firewall, the collector reads the committed rulebase through the
   vendor API (vsys or VDOM from `spec.policyScope`, default `vsys1` or
   `root`) and classifies every rule marked `eda-export-to-gbp`. All of it
   lands in the FirewallPolicyReport named after the Firewall, so whatever
   the firewall defines is visible in EDA.
2. Each address group an exported rule names maps to the GroupTag of
   exactly the same name. Names are not translated: a group named with any
   upper case (`EDA-RED`) is shown with GROUP_NAME_NOT_LOWERCASE and every
   rule that uses it is rejected, so name groups on the firewall as GroupTags
   (`eda-red`). If the operator already has that GroupTag it is used;
   otherwise the report derives it. Another invalid name is shown with
   GROUPTAG_NAME_INVALID. Where the GroupTag is attached comes from the
   operator's AssociationPolicies. A GroupTag with no AssociationPolicy is
   shown with GROUPTAG_NOT_ASSOCIATED and its rules are not translated until
   it is associated.
   Every member must be built to what the fabric can tag (v1.8.3):
   - an IPv4 prefix equal to an IRB subnet or a routed-interface subnet of the
     virtual networks. A `/32`, including a DAG registered IP, is
     HOST_MEMBER_NOT_SUPPORTED. A prefix that overlaps a subnet without
     equalling it is SUBNET_NOT_ATTACHMENT, and one outside every subnet is
     UNMANAGED_MEMBER.
   - every VLAN and bridge interface of that subnet's bridge domain (or its
     routed interface) carries the group's GroupTag and no other. None tagged
     is MEMBER_OUTSIDE_TAG_TARGETS; some untagged, or also tagged with another
     GroupTag, is SUBNET_SPLIT_ACROSS_TAGS.
   So the hosts the fabric tags are exactly the hosts the firewall rule
   matches.
3. The rules the built-in profile `microseg-1to1/1` expresses one-for-one
   become the entries of one MicroSegmentationPolicy, `fw-<firewall>`, in
   rule order, over the virtual networks where its GroupTags are attached.
   The translation is always on the report (`spec.derived`).
4. With the Firewall's Policy Generation Enabled, the report config intent
   emits the derived GroupTags and that one policy. They are derived
   resources of the report: read-only in the UI, re-asserted by EDA, and
   removed when generation goes off. The GroupTags are built even before any
   rule translates, so they can be associated.
5. Every firewall commit changes the snapshot, and therefore the
   translation. The next report write replaces the policy.

There is one switch:

| Switch | Where | Values | Effect when off |
|--------|-------|--------|-----------------|
| Policy Generation | Firewall `spec.policyGeneration` | Enabled, Disabled (default) | The translation stays on the report as a preview, and the policy is removed. Reason POLICY_GENERATION_DISABLED. |

`spec.generation` on the report says what was decided, and
`status.generation` with `status.derivedHash` what EDA committed:

| Generation | Meaning |
|------------|---------|
| Enabled | The policy is built. |
| Disabled | Policy Generation is off. Preview only. |
| Blocked | A fabric prerequisite is missing, and nothing is attempted. Today the check is that every router of a targeted virtual network is EVPNVXLAN, because the Microsegmentation app writes group-based policy under the VRF's bgp-evpn instance (ROUTER_NOT_EVPN). |
| Rejected | EDA refused the transaction: two polls after the 30 second commit wait still did not see it committed on the report's status (v1.7.1; one slow commit, as after an app install, is not a refusal). DERIVE_REJECTED gives the reason. The same translation is retried after 15 minutes; a changed one is tried on the next poll. |

Live, 2026-11-01, clab-pan-d3l (v1.8.0): report `palo-alto` derives six
GroupTags, `eda-red`, `eda-blue`, `eda-secure`, `eda-green`, `web-servers`
and `dag-web`. The only operator objects are AssociationPolicies for
`eda-red`, `eda-blue` and `eda-green` on VLANs `pan-inside`, `pan-outside`
and `fg-inside` (`examples/07-microseg-tags.yaml`). Those three groups
resolve; the other three show GROUPTAG_NOT_ASSOCIATED. The report translates
`fw-palo-alto` with 3 entries: eda-red to
eda-blue TCP 80 and 443 Accept (both directions), eda-red to eda-green Drop
(one way), over `fg-inside`, `pan-inside` and `pan-outside`. Reports
`fortigate` and `fortigate-2` show UNAVAILABLE with
VENDOR_READER_NOT_IMPLEMENTED.

Live, 2026-11-02, clab-srl-leaf-spine-dcgw (v1.8.2): the same result on
firewall-only VNETs. EDA-RED is `fw-client-pan-inside` `10.31.1.10/32`,
EDA-BLUE `fw-client-pan-outside` `10.31.2.10/32`, EDA-GREEN
`fw-client-fg-inside` `10.21.1.10/32`. The associations are on VLANs
`fw-pan-inside`, `fw-pan-outside` and `fw-fg-inside`. The report is at
`entries 3, groupTags 6, translated 2`; red, blue and green resolve, the
other three are GROUPTAG_NOT_ASSOCIATED. The GBP ACL is only in the firewall
VNETs; the DCI bridge domains carry none.

Live, 2026-11-02, clab-srl-leaf-spine-dcgw (v1.8.3): the Palo Alto was
aligned through the XML API (`scripts/fw-pan-policy-fixtures.sh align`,
commit job 4251). Static groups `eda-red`, `eda-blue` and `eda-green` hold
`10.31.1.0/24`, `10.31.2.0/24` and `10.21.1.0/24`, the IRB subnets of
`fw-pan-inside`, `fw-pan-outside` and `fw-fg-inside`, and the RED to BLUE
and RED to GREEN rules use them. RED to SECURE still names `EDA-RED` and
`EDA-SECURE` to show the rejection. The report:

| Group | State | Reasons |
|-------|-------|---------|
| `eda-red`, `eda-blue`, `eda-green` | RESOLVED | none; each `/24` IN_SCOPE |
| `EDA-RED` | NO_GROUPTAG | GROUP_NAME_NOT_LOWERCASE, HOST_MEMBER_NOT_SUPPORTED |
| `EDA-SECURE` | NO_GROUPTAG | GROUP_NAME_NOT_LOWERCASE |
| `web-servers`, `dag-web` | UNRESOLVED | GROUPTAG_NOT_ASSOCIATED, HOST_MEMBER_NOT_SUPPORTED |

`EDA-RED-to-SECURE-ALLOW` is UNSUPPORTED with GROUP_NAME_NOT_LOWERCASE for
both sides and no candidate. `fw-palo-alto` has the same 3 entries, the
committed hash equals the spec hash, the leaves carry the ACL in the three
firewall bridge domains with only `ethernet-1/31` tagged, and RED to BLUE
ping is 0% loss.

### Default action: unmatched traffic is allowed

Neither the Microsegmentation app nor SR Linux has a default-action setting.
`MicroSegmentationPolicy` has an action per entry only, and an entry without
an action allows the traffic it matches. SR Linux
`network-instance group-based-policy acl` has only `entry N action
accept|drop`. The leaves carry only the derived entries, with no catch-all,
so traffic that matches no entry is forwarded. Checked live in dcgw on 2026-11-01, while the associations were still on the DCI VNETs (they have since moved to the firewall VNETs):

| Flow | Matches an entry? | Result |
|------|-------------------|--------|
| client-1 to client-2, both RED, across VXLAN; leaf-2 learned client-1's MAC with tag 1 | no | ICMP 0% loss, TCP 22 refused by the host (delivered) |
| RED to BLUE ICMP through the Palo Alto | no (only TCP 80/443) | 0% loss |
| RED to GREEN through FortiGate 1 | entry 25 drop, but the tag does not survive the firewall hop | 0% loss, so FortiGate 1 policy decides |

So the derived policy is not an allow-list. It restricts only where it has
an explicit drop entry. A firewall's final deny rule (or allow-all) is not
exported, so it never becomes a fabric default. A default-deny fabric would
need an explicit drop entry at the end of the policy for the groups
concerned. The profile does not translate one today.

## Vendor commonality

Everything after normalisation (identity checks, classification, the
profile, translation, generation) is shared. Each vendor supplies a reader,
a normaliser and a profile:

| | Palo Alto (reader ships) | FortiGate (reader not yet) |
|-|--------------------------|----------------------------|
| API | PAN-OS XML API, `pan-os-xml-api-direct` | FortiOS REST API, `fortios-rest-api-direct` |
| Scope | vsys, default `vsys1` | VDOM, default `root` |
| Export marker | Rule tag `eda-export-to-gbp` | Policy section label (`global-label`) `eda-export-to-gbp`. FortiOS 7 policies have no tags, and the section keeps the exported rules as one ordered block. |
| Identity | Address group, static or dynamic, named like the GroupTag; dynamic members are the firewall's runtime membership | Address group (`firewall addrgrp`) named like the GroupTag; members are its address objects |
| Revision | Config audit version before and after the read | To be decided (config revision or a checksum of the read) |
| Actions | allow, deny, drop | accept, deny |
| Not translatable | App-ID, User-ID, URL category, HIP, profiles | Application control, users and groups, ISDB, UTM profiles, NAT |

A FortiGate report today shows UNAVAILABLE with
VENDOR_READER_NOT_IMPLEMENTED, with `vdom`, `section-label` and the
FortiOS API.

## From a PAN rule to an EDA policy

The Microsegmentation app does not match IP addresses. An endpoint gets a
GroupTag through an AssociationPolicy on its interface: a bridge, IRB or
routed interface, a VLAN, or a static route. A MicroSegmentationPolicy entry
matches a source GroupTag, a destination GroupTag, the IP version, the
protocol, and ports, and accepts or drops. Its `serviceTargets` are virtual
networks, routers, or bridge domains.

So a PAN rule translates only when its source and destination are
identities EDA owns. Nothing in EDA or SR Linux tags a single IP or MAC,
so since v1.8.3 a `/32` member is rejected and a member must equal the
subnet of the attachments its GroupTag is on: one security group per IRB or
routed subnet. The element-by-element mapping and the gaps are in
`eda-microsegmentation-demo/docs/FIREWALL-RULES-TO-EDA-GBP.md`.

| Step | What happens | Owner | State |
|------|--------------|-------|-------|
| 1. Discover | Read the vsys rules, objects, DAG membership, and revisions as one snapshot. | Firewall app collector | Built (v1.4.0) |
| 2. Classify | Each rule gets classification, candidate, inspection requirement, translation state, path state, and bypass authorisation, with reasons. | Firewall app collector | Built (v1.4.0) |
| 3. Identity | Each address group maps by its exact name to a GroupTag: the operator's if one exists, otherwise derived from the group. An upper-case name is rejected (GROUP_NAME_NOT_LOWERCASE). Its targets come from the operator's AssociationPolicies. Every member must equal an IRB or routed-interface subnet whose attachments all carry this GroupTag and no other (HOST_MEMBER_NOT_SUPPORTED, SUBNET_NOT_ATTACHMENT, MEMBER_OUTSIDE_TAG_TARGETS, SUBNET_SPLIT_ACROSS_TAGS, TARGET_SHARED, GROUPTAG_NOT_ASSOCIATED). Selector and static-route associations cannot be checked and block the group. The Firewall app never creates an AssociationPolicy. | Firewall app derives GroupTags; Microsegmentation app owns associations | Built (v1.8.0; strict names and subnets v1.8.3) |
| 4. Compatibility | The built-in profile `microseg-1to1/1`: IPv4, TCP/UDP destination port or range plus source port, allow or deny, one group to one group. Everything else stays NGFW_REQUIRED or UNSUPPORTED. | Firewall app | Built (v1.5.0). Not yet bound to builds by evidence. |
| 5. Translate | One ordered MicroSegmentationPolicy per Firewall, `fw-<firewall>`, in rule order, with a hash. NGFW_REQUIRED rules produce no GBP allow. | Firewall app | Built (v1.7.0) |
| 6. Approve and build | Setting the Firewall's Policy Generation to Enabled is the approval, and changes then follow the firewall. The one policy is built as a derived resource by the Microsegmentation app. No direct SR Linux writer. | Firewall app, Microsegmentation app | Built (v1.7.0) |
| 7. Drift | Derived resources cannot be edited, and EDA re-asserts them on every transaction. Source absence never deletes: an unavailable read keeps the last good translation. | EDA | By construction |

For the lab colour rules, step 5 produces `fw-palo-alto`:

| PAN rule | Entry |
|----------|-------|
| `EDA-RED-to-BLUE-ALLOW` (tcp-web: 80, 443) | sourceGroupTag `eda-red`, destinationGroupTag `eda-blue`, IPv4, TCP, destination port 80, Accept, bidirectional; the same for 443 |
| `EDA-RED-to-SECURE-ALLOW` (tcp-8443) | None: it names upper-case groups `EDA-RED` and `EDA-SECURE` (GROUP_NAME_NOT_LOWERCASE), so the rule is rejected |
| `EDA-RED-to-GREEN-DENY` (any) | `eda-red` to `eda-green`, IPv4, Drop, one way |

Default deny stays owned by the Microsegmentation app (gate F).

### What the lab still cannot do

- **Routed through the firewall.** In `pan-d3l`, RED, BLUE and GREEN sit in
  separate virtual networks routed through the firewalls, so a tag set on
  ingress does not survive the firewall hop. Enforcement (Test 5) needs
  endpoints in EVPN virtual networks with traffic on the fabric, which is
  why it moves to `clab-srl-leaf-spine-dcgw`.
- **Two colour rules translate.** RED to SECURE names upper-case groups, and the other
  six exported rules stay UNSUPPORTED or NGFW_REQUIRED for their own reasons
  (App-ID, negation, disabled, address objects instead of groups).

## Gate evidence (v0.21)

Observe-only discovery needs gates A, B, D, I and the applicable
source-health gates.

| Gate | Requirement | Lab evidence | Status |
|------|-------------|--------------|--------|
| A | Existing app source, build, regression suite | Source `Projects/eda-fw-integration/firewall`; `scripts/fw-test.sh` (go vet, go test, 25 pytest) passes. The source folder is not under version control, so there is no immutable commit reference. | OPEN (needs a commit reference) |
| A | Extends the existing app, no parallel subsystem | Same app `firewall.eda.labs`, same collector, credentials Secret, store, and report pattern. | Lab evidence |
| A | Existing onboarding, health, interface tests still pass | Same suite plus live: four interfaces Verified, Palo Alto and FortiGate 1 health 100 on 2026-11-01. No upgrade or rollback test. | OPEN (upgrade/rollback) |
| B | One PAN management mode | `pan-os-xml-api-direct`, standalone VM-50, vsys1. | Lab evidence |
| B | Exact tag `eda-export-to-gbp` is the only selector | `internal/policy` tests; live: 9 of 11 rules exported. | Lab evidence |
| B | Complete SourceSnapshot | Rules, referenced objects, effective order, membership flags; audit version before and after; sha256 source and normalised hashes; tests for incomplete, malformed, unauthorised, and changed-during-read. | Lab evidence |
| B | Disabled, negation, unsupported action, ambiguous precedence | `eda-disabled`, `eda-negated-src`, App-ID, and precedence fixtures; live reasons match. No Panorama, so no inherited rules to test. | Lab evidence (inheritance N/A, rationale: standalone firewall) |
| B | Pagination, timeouts, retry, back-off, circuit breaking | One read per section with the client timeout; retry is the next 30 s poll. No back-off or circuit breaker. | OPEN |
| B | Snapshot records revision, scope, capture time, completeness | `snapshot` in the policy report. Shared objects read; no pagination in the XML config read. | Lab evidence |
| C | Microsegmentation app northbound contract | Not supplied. The installed CRDs (`microsegmentation.eda.nokia.com/v1alpha1`) are known, but a CRD is not a versioned contract. | BLOCKED |
| D | Identity resolves uniquely to one namespace, VNET, service target, endpoint | Group name to GroupTag, derived unless the operator has one; targets from the operator's AssociationPolicies; members checked against the targets' IRB subnets. Live: EDA-RED, EDA-BLUE, EDA-GREEN RESOLVED on `eda-red`, `eda-blue`, `eda-green`. | Lab evidence |
| D | Cross-VNET, overlap, unmanaged, conflicting tags rejected | Unit tests for MEMBER_OUTSIDE_TAG_TARGETS, TARGET_SHARED, OVERLAPPING_MEMBERSHIP (tagged groups only), GROUPTAG_NOT_ASSOCIATED. Same IP in two VNETs not tested live. | OPEN |
| D | Unowned objects never adopted | GroupTags and AssociationPolicies are only read. The one written object, `fw-<firewall>`, is a derived resource of the report. | Lab evidence |
| E | Profile bound to builds; unknown never equivalent | No profile ships; every candidate is UNSUPPORTED with COMPATIBILITY_UNVALIDATED. | Lab evidence for "unknown never equivalent"; profile OPEN |
| E | PAN-only semantics never produce a broad allow | App-ID, User-ID, URL, HIP, and profile rules are NGFW_REQUIRED; `any` is UNSUPPORTED. | Lab evidence |
| F | Ordered policy set, NGFW_REQUIRED as PathRequirement only | Not built. | OPEN |
| G | Observe works, automatic disabled | Changed by user decision: discovery and translation always run; building is behind Firewall `policyGeneration: Enabled`, off by default. Disabled and Blocked build nothing. | Lab evidence (requirement changed) |
| G | Outage, partial, empty DAG, absence distinguished; absence never deletes | UNAVAILABLE keeps the last good result; STALE_SOURCE; EMPTY_MEMBERSHIP; nothing is deleted. | Lab evidence |
| H | Independent status dimensions; bypass never authorised by apply | Separate fields per rule; `bypassAuthorisation` is always NOT_AUTHORISED; `pathState` NOT_MANAGED. | Lab evidence |
| I | Correlation IDs, structured logs | `correlationId` per evaluation; JSON logs per source. No metrics. | OPEN (metrics) |
| I | Secrets never in status or logs; TLS validated | Palo Alto URL no longer leaks the key in errors (v1.4.0, with test). TLS verification is off in the lab (`insecureSkipVerify: true` on both Firewalls). | FAIL until TLS trust is configured |
| I | Least-privilege RBAC | ClusterRole `eda-fwstatus`: get/list on the kinds it reads, including GroupTags and AssociationPolicies; create/update/delete only on reports. Cluster-wide, not per namespace. | OPEN |

Recommended decision: discovery, mapping onto the operator's GroupTags, and
translation are lab-evidenced, and the policy builds in pan-d3l. Production
use is held by I (TLS) and C (no versioned Microsegmentation contract; the
app targets its v1alpha1 CRDs directly). Enforcement evidence comes from
the dcgw lab.
