# Firewall integration demo

A step-by-step run of the Firewall app (`firewall.eda.labs` v1.8.8) on EDA #2,
namespace `clab-srl-leaf-spine-dcgw`. It takes about 35 minutes. Each part
builds on the one before:

1. the app watches the firewalls;
2. EDA configures the firewall side of the fabric and confirms it;
3. firewall rules become fabric microsegmentation;
4. EDA steers the default route through the firewall;
5. a tag on a firewall rule sends a workload's traffic through the firewall
   for inspection (the quarantine segment).

Everything runs from the EDA UI at https://100.124.186.55 under
**Firewalls**, plus the Palo Alto web UI for parts 4 and 6.

This is a lab prototype. The product path is the Push Pull Provider in EDA
26.12.

## Before you start

| Check | Expected |
|-------|----------|
| Firewalls page | palo-alto, fortigate, fortigate-2 Up, Health 100 |
| Firewall Interfaces | every interface Config State Verified, Default Route empty |
| Firewall `palo-alto` | Policy Report Enabled, Policy Generation Enabled |
| Policy report `palo-alto` | Health OK, Steered 0 |
| PAN rule `EDA-WATCH-RED-HOST2` | committed, without tag `eda-watch` |

`bash scripts/fw-watch-check.sh` checks the WATCH part read-only in about a
minute: expect `steered 0` and a two-hop path from RED to host2.

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

## 4. Firewall rules become fabric microsegmentation (8 min)

1. Open **Firewall Policy Reports**. There is no Create button: the collector
   creates one report per Firewall.
2. On Firewall `palo-alto`, show the two switches:
   - **Policy Report** Enabled makes the collector read the policy.
   - **Policy Generation** Enabled builds the EDA policy from it.
3. Open report `palo-alto` and walk through:
   - **Firewall Config Version** and the snapshot: only committed config is
     read;
   - the rules tagged `eda-export-to-gbp`, the only ones counted and
     translated;
   - the address group to GroupTag mapping (`eda-red`, `eda-blue`,
     `eda-green`).
4. Show the results:
   - `EDA-RED-to-BLUE-ALLOW` becomes Accept entries for TCP 80 and 443.
   - `EDA-RED-to-GREEN-DENY` becomes a Drop entry.
   - `EDA-RED-to-SECURE-ALLOW` is **rejected** because its groups are upper
     case. The fabric tags attachments, so firewall objects have to be built
     to what EDA can tag.
5. Open the derived MicroSegmentationPolicy **`fw-palo-alto`**. It is
   read-only: EDA owns it on behalf of the report.

**Message:** the rules are defined only on the firewall. EDA enforces the
subset the fabric can enforce, and says why for the rest. Where each GroupTag
attaches stays with the operator's AssociationPolicies.

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

## 6. Quarantine for inspection: WATCH (8 min)

A security event puts a workload under watch. Its traffic must go through
the firewall for inspection, even to neighbours in the same VRF that the
fabric would normally route to directly. The trigger is a tag on a PAN
security rule.

What this shows is the **WATCH** step of the containment lifecycle: forced
inspection, with no access taken away. Fabric containment (QUARANTINED and
ISOLATED, dropping traffic at the leaf with a containment profile) is
designed but not built. See "Close" below.

The lab pieces:

| Item | Value |
|------|-------|
| PAN rule | `EDA-WATCH-RED-HOST2`: zone inside to inside, `eda-red` (10.31.1.0/24) to `eda-host2` (10.31.13.0/30), allow, log at session end |
| RED client | `fw-client-pan-inside`, 10.31.1.10 |
| host2 | 10.31.13.2, routed on srl-leaf-1 `ethernet-1/32`, same VRF, HTTP on port 80 |
| PAN inside | 10.31.11.2 |

1. **Show the direct path.** From the RED client:

   ```bash
   docker exec fw-client-pan-inside traceroute -n -q 1 -m 5 10.31.13.2
   ```

   Two hops: 10.31.1.1, then 10.31.13.2. The PAN never sees this traffic.

2. **Show the report.** Report `palo-alto`: note the Firewall Config Version
   and Steered 0.

3. **Trigger on the PAN.** In the PAN web UI, open Policies, Security,
   `EDA-WATCH-RED-HOST2`. On the General tab add tag `eda-watch`, click OK,
   then Commit. The commit takes 1 to 2 minutes.

4. **Watch EDA react.** Within about 30 seconds of the commit, the report
   shows:
   - the new Firewall Config Version;
   - under Derived, Steering, a STEERED row: 10.31.1.0/24 to 10.31.13.0/30,
     next hop 10.31.11.2;
   - Steered 1.

   EDA commits the steering straight away as derived Configlet
   `fw-steer-palo-alto-srl-leaf-1`. No one touched EDA.

5. **Show the leaf.** On srl-leaf-1:

   ```bash
   docker exec <srl-leaf-1 container> sr_cli -d "info from running network-instance fw-pan-inside-vrf policy-forwarding"
   ```

   Two policies: `fw-steer-irb0-7` on RED's IRB and
   `fw-steer-ethernet-1-32-4097` on host2's port. Each sends the other subnet
   to next-hop group `fw-steer-palo-alto`.

6. **Show the new path.** Repeat the traceroute:

   ```
   10.31.1.1 -> 10.31.11.2 (PAN) -> 10.31.1.1 -> 10.31.13.2
   ```

   The return path from host2 also goes through the PAN, so it sees the whole
   session. Ping and HTTP still work.

7. **Show the inspection.** Generate traffic:

   ```bash
   docker exec fw-client-pan-inside curl -s http://10.31.13.2/
   ```

   In the PAN UI, Monitor, Traffic: 10.31.1.10 to 10.31.13.2:80, inside to
   inside, rule `EDA-WATCH-RED-HOST2`, App-ID `web-browsing`.

8. **Release.** Remove tag `eda-watch` from the rule and Commit. Within about
   30 seconds of the commit, the Steering row is gone, Steered is 0, the
   Configlet and both leaf policies are removed, and the traceroute is two
   hops again.

**What to say about the limits:**

- **Whole subnets.** A rule redirects every host in its source and destination
  subnets, not single hosts, because EDA tags and steers attachments, not
  IPs.
- **Routed only, same VRF.** Both subnets must be routed on the same router,
  and the firewall must have an interface there. Bridged traffic inside one
  subnet cannot be policy routed on SR Linux.
- **Refusals are visible.** A rule that cannot be steered stays on the report
  as REFUSED with its reason, for example ANY_SOURCE, SAME_SUBNET,
  DIFFERENT_ROUTERS or NO_FIREWALL_INTERFACE. Nothing is half applied.
- **Prototype mechanism.** The steering is a Configlet. The product path is
  the Push Pull Provider in EDA 26.12.

If the PAN UI is slow, `bash scripts/fw-watch-pan.sh on` and
`bash scripts/fw-watch-pan.sh off` make the same tag change through the XML
API, with the commit, in 1 to 3 minutes each. The detailed runbook is
[DEMO-WATCH-STEERING.md](DEMO-WATCH-STEERING.md).

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
| PAN rule `EDA-WATCH-RED-HOST2` | committed without tag `eda-watch` |
| Report `palo-alto` | Steered 0, no `fw-steer-*` Configlet |

If a report transaction fails during WATCH, remove the tag and commit. A
Rejected report keeps its GroupTags, so the AssociationPolicies keep working
while it is retried.
