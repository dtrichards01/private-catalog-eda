# PAN policy to EDA microsegmentation

Companion to test plan v0.18 and readiness checklist v0.21. This page says
what the lab app does today, how a Palo Alto rule becomes an EDA
microsegmentation policy, and the lab evidence for each checklist gate.
Status values are the checklist's own. Only the gate owners can record PASS,
so evidenced gates are marked "lab evidence" and stay OPEN on the checklist.

## What runs today

v1.4.0 is observe only. It discovers and classifies. It does not create
GroupTags, AssociationPolicies, or MicroSegmentationPolicies, and it does
not change the firewall. The Microsegmentation app is installed on EDA #2,
but no object of any of its kinds exists in any namespace, including no
`GroupTagPoolSetup`. That is why the fabric shows nothing: no step that
writes to it has been built or authorised yet.

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
| 3. Identity | Each controlled PAN DAG maps to one EDA GroupTag, and each DAG member resolves to the EDA attachment the endpoint sits on, in the mapped virtual network. The GroupTag and its AssociationPolicy are EDA-owned and created through the Microsegmentation app. | EDA operator, Microsegmentation app | Not built. No GroupTags in the lab. |
| 4. Compatibility | A CompatibilityProfile, bound to the exact Firewall app, Microsegmentation app, EDA, and SR Linux builds, says which L3/L4 dimensions the fabric enforces equivalently. Without it nothing is FABRIC_ENFORCEABLE. | Firewall app, evidence from the dcgw lab | Not built (decision: profile later, as a ConfigMap) |
| 5. Propose | One deterministic, ordered MicroSegmentationPolicy request per scope mapping, in PAN order, with a change ID, the source revision, and a request hash. NGFW_REQUIRED rules produce a PathRequirement only, never a GBP allow. | Firewall app | Not built |
| 6. Review and apply | A person approves the exact change ID, revision, and hash. The apply goes through the Microsegmentation app contract only. No direct EDA or SR Linux writer. | Microsegmentation app contract | Blocked: contract not supplied (gate C) |
| 7. Drift | Compare MicrosegmentationPolicyState with the applied request; report APPLIED or DRIFTED. Source absence never deletes. | Firewall app | Not built |

For the lab colour rules, step 5 would produce for `pan-inside`:

| PAN rule | Entry |
|----------|-------|
| `EDA-RED-to-BLUE-ALLOW` (tcp-web: 80, 443) | sourceGroupTag `red`, destinationGroupTag `blue`, IPv4, TCP, destination port 80, Accept; the same for 443 |
| `EDA-RED-to-SECURE-ALLOW` (tcp-8443) | `red` to `secure`, IPv4, TCP, destination port 8443, Accept |
| `EDA-RED-to-GREEN-DENY` (any) | `red` to `green`, IPv4, Drop |

Default deny stays owned by the Microsegmentation app (gate F).

### Why the lab rules are not eligible

- **No identities.** GroupTags `red`, `blue`, `green`, and `secure` do not
  exist, so every DAG reports `GROUPTAG_NOT_FOUND` and the rules
  `IDENTITY_UNRESOLVED`.
- **Wrong scope for the lab shape.** In `pan-d3l`, client1 (RED) is in
  `pan-inside`, client2 (BLUE) in `pan-outside`, and client3 (GREEN) behind
  FortiGate 1 in `fg-inside`. Each zone is its own virtual network, routed
  through the firewall. A fabric policy scoped to `pan-inside` cannot match
  members in another virtual network, so they are `CROSS_SCOPE_MEMBER`.
  Test 5 needs endpoints in one virtual network with east-west traffic on
  the fabric. That is the reason for the planned move to
  `clab-srl-leaf-spine-dcgw`.
- **Prefix members.** SECURE is `10.31.2.0/24`. A prefix maps to a static
  route or a whole bridge domain, not one endpoint (`PREFIX_MEMBER_NOT_IN_V1`).
- **No profile.** `COMPATIBILITY_UNVALIDATED` on every candidate.

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
| G | Observe works, automatic disabled | `mode` enum is `observe` only. | Lab evidence |
| G | Outage, partial, empty DAG, absence distinguished; absence never deletes | UNAVAILABLE keeps the last good result; STALE_SOURCE; EMPTY_MEMBERSHIP; nothing is deleted. | Lab evidence |
| H | Independent status dimensions; bypass never authorised by apply | Separate fields per rule; `bypassAuthorisation` is always NOT_AUTHORISED; `pathState` NOT_MANAGED. | Lab evidence |
| I | Correlation IDs, structured logs | `correlationId` per evaluation; JSON logs per source. No metrics. | OPEN (metrics) |
| I | Secrets never in status or logs; TLS validated | Palo Alto URL no longer leaks the key in errors (v1.4.0, with test). TLS verification is off in the lab (`insecureSkipVerify: true` on both Firewalls). | FAIL until TLS trust is configured |
| I | Least-privilege RBAC | ClusterRole `eda-fwstatus`: get/list on the kinds it reads, create/update only on reports. Cluster-wide, not per namespace. | OPEN |

Recommended observe-only decision: **OBSERVE/REVIEW ONLY** remains blocked
on D (identities) and I (TLS). Reviewed apply is blocked on C, E, F, and G.
Automatic mode is disabled as required.
