# Firewall policy to EDA microsegmentation

Companion to test plan v0.18 and readiness checklist v0.21. This page says
what the lab app does today, how a Palo Alto rule becomes an EDA
microsegmentation policy, and the lab evidence for each checklist gate.
Status values are the checklist's own. Only the gate owners can record PASS,
so evidenced gates are marked "lab evidence" and stay OPEN on the checklist.

## What runs today (v1.7.0)

Policy is defined on the firewall, learnt in EDA, translated onto the
existing microsegmentation GroupTags, and built. The Microsegmentation app
stays the owner of GroupTags and AssociationPolicies, and operators can keep
writing their own MicroSegmentationPolicies next to the firewall's.

1. For every Firewall, the collector reads the committed rulebase through the
   vendor API (vsys or VDOM from `spec.policyScope`, default `vsys1` or
   `root`) and classifies every rule marked `eda-export-to-gbp`. All of it
   lands in the FirewallPolicyReport named after the Firewall, so whatever
   the firewall defines is visible in EDA.
2. Each address group an exported rule names maps to the GroupTag of the
   same name in lower case: Palo Alto `EDA-RED` is GroupTag `eda-red`. The
   GroupTag must already exist. Where it is attached comes from the
   operator's AssociationPolicies, and every firewall member must sit in an
   IRB subnet of those attachments, so the fabric tags the hosts the firewall
   rule matches. A group with no GroupTag is shown with NO_GROUPTAG and its
   rules are not translated.
3. The rules the built-in profile `microseg-1to1/1` expresses one-for-one
   become the entries of one MicroSegmentationPolicy, `fw-<firewall>`, in
   rule order, over the virtual networks where its GroupTags are attached.
   The translation is always on the report (`spec.derived`).
4. With the Firewall's Policy Generation Enabled, the report config intent
   emits that one policy. It is a derived resource of the report: read-only
   in the UI, re-asserted by EDA, and removed when generation goes off.
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
| Rejected | EDA refused the transaction, or did not commit it within the commit wait. DERIVE_REJECTED gives the reason. The same translation is retried after 15 minutes; a changed one is tried on the next poll. |

Live, 2026-11-01, clab-pan-d3l: the operator objects are GroupTags
`eda-red`, `eda-blue` and `eda-green` (Global) with AssociationPolicies on
VLANs `pan-inside`, `pan-outside` and `fg-inside`
(`examples/07-microseg-tags.yaml`). Report `palo-alto` maps EDA-RED, EDA-BLUE
and EDA-GREEN to them, shows EDA-SECURE, `web-servers` and `dag-web` with
NO_GROUPTAG, and translates `fw-palo-alto` with 3 entries: eda-red to
eda-blue TCP 80 and 443 Accept (both directions), eda-red to eda-green Drop
(one way), over `fg-inside`, `pan-inside` and `pan-outside`. Reports
`fortigate` and `fortigate-2` show UNAVAILABLE with
VENDOR_READER_NOT_IMPLEMENTED.

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
identities EDA owns:

| Step | What happens | Owner | State |
|------|--------------|-------|-------|
| 1. Discover | Read the vsys rules, objects, DAG membership, and revisions as one snapshot. | Firewall app collector | Built (v1.4.0) |
| 2. Classify | Each rule gets classification, candidate, inspection requirement, translation state, path state, and bypass authorisation, with reasons. | Firewall app collector | Built (v1.4.0) |
| 3. Identity | Each address group maps by name, lower case, to an existing GroupTag. Its targets come from the operator's AssociationPolicies, and every member must sit in an IRB subnet of them (MEMBER_OUTSIDE_TAG_TARGETS, TARGET_SHARED, GROUPTAG_NOT_ASSOCIATED). Selector, routed-interface and static-route associations cannot be checked and block the group. The Firewall app never creates a GroupTag or AssociationPolicy. | Microsegmentation app owns; Firewall app reads | Built (v1.7.0) |
| 4. Compatibility | The built-in profile `microseg-1to1/1`: IPv4, TCP/UDP destination port or range plus source port, allow or deny, one group to one group. Everything else stays NGFW_REQUIRED or UNSUPPORTED. | Firewall app | Built (v1.5.0). Not yet bound to builds by evidence. |
| 5. Translate | One ordered MicroSegmentationPolicy per Firewall, `fw-<firewall>`, in rule order, with a hash. NGFW_REQUIRED rules produce no GBP allow. | Firewall app | Built (v1.7.0) |
| 6. Approve and build | Setting the Firewall's Policy Generation to Enabled is the approval, and changes then follow the firewall. The one policy is built as a derived resource by the Microsegmentation app. No direct SR Linux writer. | Firewall app, Microsegmentation app | Built (v1.7.0) |
| 7. Drift | Derived resources cannot be edited, and EDA re-asserts them on every transaction. Source absence never deletes: an unavailable read keeps the last good translation. | EDA | By construction |

For the lab colour rules, step 5 produces `fw-palo-alto`:

| PAN rule | Entry |
|----------|-------|
| `EDA-RED-to-BLUE-ALLOW` (tcp-web: 80, 443) | sourceGroupTag `eda-red`, destinationGroupTag `eda-blue`, IPv4, TCP, destination port 80, Accept, bidirectional; the same for 443 |
| `EDA-RED-to-SECURE-ALLOW` (tcp-8443) | None: there is no GroupTag `eda-secure` (NO_GROUPTAG) |
| `EDA-RED-to-GREEN-DENY` (any) | `eda-red` to `eda-green`, IPv4, Drop, one way |

Default deny stays owned by the Microsegmentation app (gate F).

### What the lab still cannot do

- **Routed through the firewall.** In `pan-d3l`, RED, BLUE and GREEN sit in
  separate virtual networks routed through the firewalls, so a tag set on
  ingress does not survive the firewall hop. Enforcement (Test 5) needs
  endpoints in EVPN virtual networks with traffic on the fabric, which is
  why it moves to `clab-srl-leaf-spine-dcgw`.
- **Two colour rules translate.** EDA-SECURE has no GroupTag, and the other
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
| D | Identity resolves uniquely to one namespace, VNET, service target, endpoint | Group name to existing GroupTag; targets from the operator's AssociationPolicies; members checked against the targets' IRB subnets. Live: EDA-RED, EDA-BLUE, EDA-GREEN RESOLVED on `eda-red`, `eda-blue`, `eda-green`. | Lab evidence |
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
