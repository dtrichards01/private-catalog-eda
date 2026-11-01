# Firewall policy to EDA microsegmentation

Companion to test plan v0.18 and readiness checklist v0.21. This page says
what the lab app does today, how a Palo Alto rule becomes an EDA
microsegmentation policy, and the lab evidence for each checklist gate.
Status values are the checklist's own. Only the gate owners can record PASS,
so evidenced gates are marked "lab evidence" and stay OPEN on the checklist.

## What runs today (v1.6.1)

The process is: rules are defined on the firewall, the Firewall app
translates them, and the Microsegmentation app builds the objects. Nothing
is reinterpreted on the way, and the built objects are derived (read-only)
resources of the Firewall app.

1. The collector reads the committed rulebase through the vendor API and
   classifies every rule marked `eda-export-to-gbp`.
2. With the FirewallPolicySource in `mode: derive`, it translates the rules
   the built-in profile `microseg-1to1/1` can express one-for-one, and writes
   the translation into the FirewallPolicyReport (`spec.derived`).
3. The report config intent emits one GroupTag per used binding, one
   AssociationPolicy per binding (on its named VLANs or bridge interfaces),
   and one MicroSegmentationPolicy `fwpol-<source>`. It does this only when
   the report says `generation: Enabled`. The Microsegmentation app builds
   them on the nodes. In the EDA UI they show as derived from the report and
   cannot be edited.
4. Every firewall commit changes the snapshot, and therefore the
   translation. The next report write replaces the derived set, and EDA
   removes whatever is no longer emitted.

There are two switches, and both must be on:

| Switch | Where | Values | Effect when off |
|--------|-------|--------|-----------------|
| Policy Generation | Firewall `spec.policyGeneration` | Enabled, Disabled (default) | The translation is kept on the report as a preview; nothing is built, and anything built is removed. Reason POLICY_GENERATION_DISABLED. |
| Mode | FirewallPolicySource `spec.mode` | observe (default), derive | observe: no translation at all. |

`status.generation` on the source says what happened:

| Generation | Meaning |
|------------|---------|
| Enabled | EDA committed the derived objects. |
| Disabled | The Firewall's Policy Generation is off. Preview only. |
| Blocked | A fabric prerequisite is missing, and nothing is attempted. Today the check is that every router of a targeted virtual network is EVPNVXLAN, because the Microsegmentation app writes group-based policy under the VRF's bgp-evpn instance (ROUTER_NOT_EVPN). |
| Rejected | EDA refused the transaction. DERIVE_REJECTED gives the reason. The same translation is retried after 15 minutes; a changed one is tried on the next poll. |

Live, 2026-11-01, clab-pan-d3l: the source is in derive. The translation
has 3 GroupTags (`red`, `blue`, `green`, Global, because three VNETs are in
scope), 3 AssociationPolicies on VLANs `pan-inside`, `pan-outside` and
`fg-inside`, and one policy with 3 entries: red to blue TCP 80 Accept, red
to blue TCP 443 Accept, red to green Drop. With Policy Generation Enabled
it is Blocked, because all four pan-d3l VRFs are `type: Simple`. The
Firewall is left Disabled. Before v1.6.1 the same translation was sent to
EDA and refused, with
`.network-instance{pan-inside-vrf}.protocols.bgp-evpn.bgp-instance{1}:
cannot update object that does not exist` on leaf1 and leaf2. That
transaction was atomic, so the fabric did not change. Enforcement is shown
in `clab-srl-leaf-spine-dcgw`, where the routers are EVPNVXLAN.

## Vendor commonality

Everything after normalisation (identity checks, classification, the
profile, translation, generation) is shared. Each vendor supplies a reader,
a normaliser and a profile:

| | Palo Alto (reader ships) | FortiGate (reader not yet) |
|-|--------------------------|----------------------------|
| API | PAN-OS XML API, `pan-os-xml-api-direct` | FortiOS REST API, `fortios-rest-api-direct` |
| Scope | vsys, default `vsys1` | VDOM, default `root` |
| Export marker | Rule tag `eda-export-to-gbp` | Policy section label (`global-label`) `eda-export-to-gbp`. FortiOS 7 policies have no tags, and the section keeps the exported rules as one ordered block. |
| Identity | Dynamic address group whose filter is exactly one controlled tag; runtime members from the firewall | Address group (`firewall addrgrp`); members are its address objects |
| Revision | Config audit version before and after the read | To be decided (config revision or a checksum of the read) |
| Actions | allow, deny, drop | accept, deny |
| Not translatable | App-ID, User-ID, URL category, HIP, profiles | Application control, users and groups, ISDB, UTM profiles, NAT |

A FortiGate source today reports UNAVAILABLE with
VENDOR_READER_NOT_IMPLEMENTED, and its status shows `vdom`,
`section-label` and the FortiOS API.

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
| 3. Identity | Each controlled address group maps to one EDA GroupTag. Each binding names its VLANs or bridge interfaces, and every member must sit in a subnet of their bridge domain (MEMBER_OUTSIDE_TARGETS, TARGET_SHARED, TARGET_OUT_OF_SCOPE). In derive mode the GroupTag is built unless an operator already made it. | Firewall app | Built (v1.5.0) |
| 4. Compatibility | The built-in profile `microseg-1to1/1`: IPv4, TCP/UDP destination port or range plus source port, allow or deny, one group to one group. Everything else stays NGFW_REQUIRED or UNSUPPORTED. | Firewall app | Built (v1.5.0). Not yet bound to builds by evidence. |
| 5. Translate | One ordered MicroSegmentationPolicy per source, in rule order, with the source revision and a hash. NGFW_REQUIRED rules produce no GBP allow. | Firewall app | Built (v1.5.0) |
| 6. Approve and build | The user decision replaces per-change review: switching the source to derive and the Firewall's Policy Generation to Enabled is the approval, and changes then follow the firewall. The objects are built as derived resources by the Microsegmentation app. No direct SR Linux writer. | Firewall app, Microsegmentation app | Built (v1.6.1). Blocked in pan-d3l (Simple routers). |
| 7. Drift | Derived resources cannot be edited, and EDA re-asserts them on every transaction. Source absence never deletes: an unavailable read keeps the last good translation. | EDA | By construction |

For the lab colour rules, step 5 would produce for `pan-inside`:

| PAN rule | Entry |
|----------|-------|
| `EDA-RED-to-BLUE-ALLOW` (tcp-web: 80, 443) | sourceGroupTag `red`, destinationGroupTag `blue`, IPv4, TCP, destination port 80, Accept; the same for 443 |
| `EDA-RED-to-SECURE-ALLOW` (tcp-8443) | `red` to `secure`, IPv4, TCP, destination port 8443, Accept |
| `EDA-RED-to-GREEN-DENY` (any) | `red` to `green`, IPv4, Drop |

Default deny stays owned by the Microsegmentation app (gate F).

### What the lab still cannot do

- **Simple routers.** All four pan-d3l VRFs are `type: Simple`, with no
  bgp-evpn instance, so generation is Blocked.
- **Routed through the firewall.** In `pan-d3l`, RED, BLUE and GREEN sit in
  separate virtual networks routed through the firewalls, so a tag set on
  ingress does not survive the firewall hop. Enforcement (Test 5) needs
  endpoints in EVPN virtual networks with traffic on the fabric, which is
  why it moves to `clab-srl-leaf-spine-dcgw`.
- **Prefix members.** SECURE is `10.31.2.0/24` and overlaps BLUE. It is left
  unbound in derive mode, so `EDA-RED-to-SECURE-ALLOW` is not translated.
- **Three colour rules translate.** The other six exported rules stay
  UNSUPPORTED or NGFW_REQUIRED for their own reasons (App-ID, negation,
  disabled, uncontrolled identities).

## Gate evidence (v0.21)

Observe-only discovery needs gates A, B, D, I and the applicable
source-health gates.

| Gate | Requirement | Lab evidence | Status |
|------|-------------|--------------|--------|
| A | Existing app source, build, regression suite | Source `Projects/eda-fw-integration/firewall`; `scripts/fw-test.sh` (go vet, go test, 21 pytest) passes. The source folder is not under version control, so there is no immutable commit reference. | OPEN (needs a commit reference) |
| A | Extends the existing app, no parallel subsystem | Same app `firewall.eda.labs`, same collector, credentials Secret, store, and report pattern. | Lab evidence |
| A | Existing onboarding, health, interface tests still pass | Same suite plus live: four interfaces Verified, Palo Alto and FortiGate 1 health 100 on 2026-11-01. No upgrade or rollback test. | OPEN (upgrade/rollback) |
| B | One PAN management mode | `pan-os-xml-api-direct`, standalone VM-50, vsys1. | Lab evidence |
| B | Exact tag `eda-export-to-gbp` is the only selector | `internal/policy` tests; live: 9 of 11 rules exported. | Lab evidence |
| B | Complete SourceSnapshot | Rules, referenced objects, effective order, membership flags; audit version before and after; sha256 source and normalised hashes; tests for incomplete, malformed, unauthorised, and changed-during-read. | Lab evidence |
| B | Disabled, negation, unsupported action, ambiguous precedence | `eda-disabled`, `eda-negated-src`, App-ID, and precedence fixtures; live reasons match. No Panorama, so no inherited rules to test. | Lab evidence (inheritance N/A, rationale: standalone firewall) |
| B | Pagination, timeouts, retry, back-off, circuit breaking | One read per section with the client timeout; retry is the next 30 s poll. No back-off or circuit breaker. | OPEN |
| B | Snapshot records revision, scope, capture time, completeness | `snapshot` in the policy report. Shared objects read; no pagination in the XML config read. | Lab evidence |
| C | Microsegmentation app northbound contract | Not supplied. The installed CRDs (`microsegmentation.eda.nokia.com/v1alpha1`) are known, but a CRD is not a versioned contract. | BLOCKED |
| D | Identity resolves uniquely to one namespace, VNET, service target, endpoint | Resolver checks VNET IRB subnets, ambiguity, unmanaged members, multiple identities. GroupTags do not exist in the lab. | BLOCKED (no GroupTags) |
| D | Cross-VNET, overlap, unmanaged, conflicting tags rejected | Unit tests; live `CROSS_SCOPE_MEMBER` and `OVERLAPPING_MEMBERSHIP` for BLUE and SECURE. Same IP in two VNETs not tested live. | OPEN |
| D | Unowned objects never adopted | Nothing is written. | N/A in observe mode |
| E | Profile bound to builds; unknown never equivalent | No profile ships; every candidate is UNSUPPORTED with COMPATIBILITY_UNVALIDATED. | Lab evidence for "unknown never equivalent"; profile OPEN |
| E | PAN-only semantics never produce a broad allow | App-ID, User-ID, URL, HIP, and profile rules are NGFW_REQUIRED; `any` is UNSUPPORTED. | Lab evidence |
| F | Ordered policy set, NGFW_REQUIRED as PathRequirement only | Not built. | OPEN |
| G | Observe works, automatic disabled | Changed by user decision: automatic is allowed behind two switches, source `mode: derive` and Firewall `policyGeneration: Enabled`, both off by default. Live: Disabled and Blocked build nothing. | Lab evidence (requirement changed) |
| G | Outage, partial, empty DAG, absence distinguished; absence never deletes | UNAVAILABLE keeps the last good result; STALE_SOURCE; EMPTY_MEMBERSHIP; nothing is deleted. | Lab evidence |
| H | Independent status dimensions; bypass never authorised by apply | Separate fields per rule; `bypassAuthorisation` is always NOT_AUTHORISED; `pathState` NOT_MANAGED. | Lab evidence |
| I | Correlation IDs, structured logs | `correlationId` per evaluation; JSON logs per source. No metrics. | OPEN (metrics) |
| I | Secrets never in status or logs; TLS validated | Palo Alto URL no longer leaks the key in errors (v1.4.0, with test). TLS verification is off in the lab (`insecureSkipVerify: true` on both Firewalls). | FAIL until TLS trust is configured |
| I | Least-privilege RBAC | ClusterRole `eda-fwstatus`: get/list on the kinds it reads, create/update only on reports. Cluster-wide, not per namespace. | OPEN |

Recommended decision: discovery and translation are lab-evidenced. Building
on the fabric is blocked in pan-d3l by its Simple routers and in general by
I (TLS) and C (no versioned Microsegmentation contract; the app targets its
v1alpha1 CRDs directly). Enforcement evidence comes from the dcgw lab.
