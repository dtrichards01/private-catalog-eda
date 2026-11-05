# Firewall integration demo

A step-by-step run of the Firewall app (`firewall.eda.labs` v1.8.9) on EDA #2,
namespace `clab-srl-leaf-spine-dcgw`. It takes about 35 minutes. Each part
builds on the one before:

1. the app watches the firewalls;
2. EDA configures the firewall side of the fabric and confirms it;
3. firewall rules become fabric microsegmentation;
4. EDA steers the default route through the firewall;
5. a runtime tag on one workload IP sends its traffic through the firewall
   for inspection (hybrid WATCH).

Parts 4 and 6 follow the layered runbook
[DEMO-HYBRID-WATCH.md](DEMO-HYBRID-WATCH.md), which builds the PAN rules from
an empty rule base and resets the lab at the end.

Everything runs from the EDA UI at https://100.124.186.55 under
**Firewalls**, plus the Palo Alto web UI for parts 4 and 6.

This is a lab prototype, not a product. A product needs the Push Pull
Provider first; development work for the FW Integration App is tracked for
sometime in 2027.

## Before you start

| Check | Expected |
|-------|----------|
| Firewalls page | palo-alto, fortigate, fortigate-2 Up, Health 100 |
| Firewall Interfaces | every interface Config State Verified, Default Route empty |
| Firewall `palo-alto` | Policy Report Enabled, Policy Generation Enabled |
| Policy report `palo-alto` | Health OK, Exported 0, Steered 0 |
| PAN rules | `lab-untagged` and `allow-all` only |

`bash scripts/fw-demo.sh baseline` puts the PAN and EDA in that state.

Avoid FortiGate FabricStatic live. FortiGate 1's default exits through
port1 management NAT, so it shows the `DEFAULT_EXITS_VIA_MANAGEMENT`
warning.

## 1. Set the scene (2 min)

**Message:** EDA treats the firewall as part of the fabric service, not as a
separate box.

**Show** the lab layout:

| Firewall | Inside | Outside |
|----------|--------|---------|
| Palo Alto | `fw-pan-inside` on srl-leaf-1 | `fw-pan-outside` on srl-leaf-4 |
| FortiGate 1 | `fw-fg-inside` on srl-leaf-3 | `fw-fg-outside` on srl-leaf-2 |
| FortiGate 2 | EVPN VTEP peering with the spines | |

Each firewall NIC is a /30 transit link with eBGP to the leaf. The inside and
outside VRFs share no routes, so traffic has to cross the firewall.

## 2. Monitoring through the vendor API (3 min)

1. Open **Firewalls**. Show palo-alto, fortigate and fortigate-2 with their
   state and Health.
2. Point at **Health Reason**. It names each interface that is not up and why,
   for example a BGP session in Active.
3. On the **Queries** page, run:

   ```
   .namespace.resources.cr.firewall_eda_labs.v1alpha1.firewall fields [ name, status.operationalState, status.health ]
   ```

**Message:** nothing here uses SSH or the CLI. The collector reads each
vendor's REST or XML API and writes the status into EDA, so EQL can query it
like any other EDA state.

## 3. Firewall Interfaces: EDA builds the firewall side (5 min)

1. Open **Firewall Interfaces** and show the six NICs.
2. Open `palo-alto-inside`. Walk through the attachment (leaf, port, VNET), the
   BGP fields (Fabric AS, Firewall AS) and **Configure Firewall**.
3. Open Edit without saving. The NIC name and Tenant dropdowns are filled from
   what the collector read off the firewall (Firewall Inventory).
4. Show Config State **Verified**: the firewall's committed config matches the
   spec, not just that the API call returned OK.
5. **Contrast:** `fortigate-2-local` and `fortigate-2-remote` use Advanced
   Networking, where the FortiGate is an EVPN VTEP peering with the spines.

## 4. Firewall rules become fabric microsegmentation (13 min)

Run steps 1 to 3 of [DEMO-HYBRID-WATCH.md](DEMO-HYBRID-WATCH.md):

1. **PAN rules.** Groups `eda-red`, `eda-blue`, `eda-green` (one subnet each
   of VNET `fw-pan-inside`) and four rules tagged `eda-export-to-gbp`: RED to
   BLUE web allow, RED to BLUE SSH deny, BLUE to GREEN web allow, RED to GREEN
   deny. The report shows the GroupTags derived but not yet associated.
2. **AssociationPolicies.** The operator attaches each GroupTag to its VLAN.
   The read-only MicroSegmentationPolicy `fw-palo-alto` gets six entries.
3. **Data path.** From red-1 and red-2, web to blue-1 works, SSH to blue-1
   goes from refused by host to dropped at the leaf, and everything to
   green-1 is dropped. The PAN traffic log shows none of it.

Show the two switches on Firewall `palo-alto` first: **Policy Report**
Enabled makes the collector read the policy, **Policy Generation** Enabled
builds the EDA policy from it. Point out the Firewall Config Version: only
committed config is read.

**Message:** the rules are defined only on the firewall. EDA enforces the
subset the fabric can enforce, and says why for the rest (for example
`PRECEDENCE_AMBIGUOUS` for "allow web, deny everything", which GBP cannot
express without rule order). Where each GroupTag attaches stays with the
operator's AssociationPolicies.

## 5. Default route through the firewall (10 min)

Use `palo-alto-inside`. Each status change takes 1 to 2 minutes to show.

1. **FabricStatic.** Edit the interface, set Default Route Mode to
   FabricStatic, and save.
   - Status becomes **Configured**. The note says the firewall has no default
     of its own, which is honest about what happens to the traffic next.
   - On srl-leaf-1, `show network-instance fw-pan-inside-vrf route-table ipv4-unicast summary` shows
     `0.0.0.0/0` static via 10.31.11.2.
   - Nothing is written to the firewall in this mode.
2. **FirewallBGP.** Change the mode to FirewallBGP with Firewall Next Hop
   10.31.12.1. Warn the audience first: the PAN commit restarts its BGP
   sessions for under a minute.
   - Status goes **Pending**, then **Advertised**: the firewall advertises
     0.0.0.0/0 to 10.31.11.1 only.
   - The srl-leaf-1 default becomes a BGP route from the Palo Alto. srl-leaf-4
     (outside) gets no default and keeps its routes.
   - Optionally, show the `eda-default` objects and peer group in the PAN UI,
     created through the API.
3. **Guardrail.** Set `fortigate-inside` to FirewallBGP.
   - It shows **Blocked**, `MANAGEMENT_VDOM`: root is the management VDOM,
     so its default is the management path.
   - Nothing was sent to the FortiGate. FabricStatic is the option there until
     it has a data VDOM.
4. **Clean up.** Set both interfaces back to None and wait until
   `palo-alto-inside` shows no Default Route status. The PAN `eda-default`
   objects are removed and the leaf default disappears once the PAN commit
   finishes, a few minutes on this lab PAN.

Finish this cleanup before part 6. The WATCH steering writes static routing
in `fw-pan-inside-vrf`, and a FabricStatic default in the same VRF is not
supported alongside it.

## 6. Per-host inspection: hybrid WATCH (15 min)

A security event puts one workload under watch. Its traffic must go through
the firewall for inspection, even to neighbours in the same VRF that the
fabric would normally route to directly.

Run steps 4 to 8 of [DEMO-HYBRID-WATCH.md](DEMO-HYBRID-WATCH.md):

1. **Arm.** On the PAN, dynamic group `eda-watched` (match
   `'eda-security-watch'`) and rule `EDA-WATCH-RED` (`eda-watched` to
   `eda-blue` and `eda-green`), tagged `eda-watch`, deny. The report shows
   the row **ARMED**, `NO_MEMBERS`.
2. **Watch.** Register red-1, 10.31.1.10, with tag `eda-security-watch`
   through the User-ID API. No commit. In under a minute two rows are
   **STEERED**, 10.31.1.10/32 to BLUE and to GREEN, and srl-leaf-1 has three
   forwarding policies.
3. **Test.** All of red-1's traffic to BLUE and GREEN now crosses the PAN,
   which enforces the same rules: web allowed by `EDA-RED-to-BLUE-WEB` with
   App-ID `web-browsing`, SSH and GREEN denied by the exported deny rules,
   and ping, which the fabric allowed, denied by `EDA-WATCH-RED`. red-2, in
   the same subnet, still goes direct.
4. **Guard (optional).** Set the watch rule to allow: the collector warns
   `WATCH_FALLTHROUGH_ALLOW`.
5. **Release.** Unregister the IP; the steering is removed in under a minute.

What this shows is the **WATCH** step of the containment lifecycle: forced
inspection, with no access taken away beyond the policy. Fabric containment
(QUARANTINED and ISOLATED) is designed but not built. See "Close" below.

The rule-tag variant from v1.8.8 (steer whole subnets by tagging a committed
rule) still works; [DEMO-WATCH-STEERING.md](DEMO-WATCH-STEERING.md) describes
it, on hosts that are now retired.

## 7. Close (2 min)

Through the vendor API only, the app covers:

- **observe:** firewall health, interfaces and BGP;
- **configure and confirm:** NICs, BGP and apply verification;
- **cross-domain intent:** firewall policy to microsegmentation, default
  route steering, and WATCH inspection triggered from a firewall rule.

**Next: fabric quarantine.** The same pattern extends to the rest of the
containment lifecycle (NORMAL, WATCH, QUARANTINED, ISOLATED, RECOVERING,
RELEASED). QUARANTINED would move the workload's attachment to a quarantine
GroupTag and build a containment policy: allow DNS, NTP and remediation,
drop everything else in both directions at the leaf. ISOLATED drops all
non-exempt traffic. Dropping at the fabric contains lateral movement next to
the workload instead of carrying the traffic to the firewall just to drop it.
Release would always need an explicit operator approval.

## Back to stable

| Item | State |
|------|-------|
| Firewall Interfaces | Default Route None on all |
| PAN and EDA | `bash scripts/fw-demo.sh baseline`: PAN rules `lab-untagged` and `allow-all` only, no registered IPs, no demo AssociationPolicies |
| Report `palo-alto` | Exported 0, Steered 0, no `fw-steer-*` Configlet |

If a report transaction fails during WATCH, unregister the IP. A
Rejected report keeps its GroupTags, so the AssociationPolicies keep working
while it is retried.
