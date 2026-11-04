# Demo: steer traffic through the Palo Alto with a rule tag

Tag a Palo Alto security rule `eda-watch`, commit, and EDA sends the traffic
between the rule's source and destination subnets through the firewall in
both directions. Remove the tag and commit to put the path back. No DAG and
no EDA change are needed: the firewall rule is the only input.

Lab: EDA #2, namespace `clab-srl-leaf-spine-dcgw`, app `firewall.eda.labs`
v1.8.8. How it works is in README, WATCH steering.

`bash scripts/fw-demo.sh baseline` deletes `EDA-WATCH-RED-HOST2` and the
fixture groups this runbook uses. The current demo, with per-host watch by
runtime tag, is [DEMO-HYBRID-WATCH.md](DEMO-HYBRID-WATCH.md). To run this one
after a baseline, run `bash scripts/fw-demo.sh rules` and
`bash scripts/fw-demo.sh associate` (group `eda-red`), then
`bash scripts/fw-watch-pan.sh stage` (the rule).

## Starting state

| Item | Value |
|------|-------|
| Firewall | `palo-alto`, Policy Report Enabled, Policy Generation Enabled |
| PAN rule | `EDA-WATCH-RED-HOST2`, committed without the tag, above `lab-untagged` |
| Rule match | zone inside to inside, `eda-red` (10.31.1.0/24) to `eda-host2` (10.31.13.0/30), any application, any service, allow, log at session end |
| RED client | `fw-client-pan-inside`, 10.31.1.10, gateway 10.31.1.1 (IRB of `fw-pan-inside`) |
| host2 | 10.31.13.2, routed subnet on `srl-leaf-1` `ethernet-1/32` in the same VRF, network instance `fw-pan-inside-vrf` (HTTP on port 80) |
| PAN inside | 10.31.11.2 in `fw-pan-inside-vrf` |

Check before you start (about 1 minute, read-only):

```bash
bash scripts/fw-watch-check.sh
```

Expect `steered 0`, no `fw-steer-*` policy on `srl-leaf-1`, and a two-hop
path: `10.31.1.1`, then `10.31.13.2`.

## Steps

1. **Show the direct path.** From the RED client, traceroute to host2:

   ```bash
   docker exec fw-client-pan-inside traceroute -n -q 1 -m 5 10.31.13.2
   ```

   Two hops, and the PAN never sees this traffic. RED and host2 are in the
   same VRF, so the leaf routes between them directly.

2. **Show the report in EDA.** Open Firewall Policy Reports, `palo-alto`.
   Note the Firewall Config Version and Steered 0.

3. **Tag the rule on the Palo Alto.** In the PAN web UI, open Policies,
   Security, `EDA-WATCH-RED-HOST2`, and add tag `eda-watch` on the General
   tab. Click OK, then Commit.

   The commit takes 1 to 2 minutes on this VM. It restarts the PAN BGP
   sessions briefly, which does not affect this flow.

4. **Watch EDA pick it up.** Within about 30 seconds of the commit, the report
   shows:
   - the new Firewall Config Version;
   - under Derived, Steering, one STEERED row: 10.31.1.0/24 to 10.31.13.0/30,
     the router both subnets share, next hop 10.31.11.2;
   - Steered 1 in the status.

   Policy Generation is Enabled, so EDA commits the steering straight away as
   a derived Configlet, `fw-steer-palo-alto-srl-leaf-1`.

5. **Show the leaf.** On `srl-leaf-1`:

   ```bash
   docker exec <srl-leaf-1 container> sr_cli -d "info from running network-instance fw-pan-inside-vrf policy-forwarding"
   ```

   Two policies, `fw-steer-irb0-7` (from RED) and
   `fw-steer-ethernet-1-32-4097` (from host2), each sending the other
   subnet to next-hop group `fw-steer-palo-alto`.

6. **Show the new path.** Repeat the traceroute:

   ```
   10.31.1.1 -> 10.31.11.2 (PAN) -> 10.31.1.1 -> 10.31.13.2
   ```

   The return path from host2 to RED also goes through 10.31.11.2. Ping and
   HTTP still work.

7. **Show the PAN inspecting it.** Generate some traffic:

   ```bash
   docker exec fw-client-pan-inside curl -s http://10.31.13.2/
   ```

   In the PAN UI, Monitor, Traffic (or the session browser), the session
   10.31.1.10 to 10.31.13.2:80 matches rule `EDA-WATCH-RED-HOST2`,
   zone inside to inside, App-ID `web-browsing`.

8. **Stop watching.** Remove tag `eda-watch` from the rule and Commit. Within
   about 30 seconds of the commit the Steering row is gone, Steered is 0, the
   Configlet and both leaf policies are removed, and the traceroute is two
   hops again.

## What to say about the limits

- **Whole subnets.** A rule redirects every host in its source and
  destination subnets, not single hosts. Address groups must equal IRB or
  routed-interface subnets.
- **Routed only, same VRF.** Both subnets must be routed on the same EDA
  router, and the firewall must have an interface in it. Bridged traffic
  inside one subnet cannot be policy routed.
- **Refusals are visible.** Any rule that cannot be steered stays on the
  report as REFUSED with its reason, for example ANY_SOURCE, SAME_SUBNET,
  DIFFERENT_ROUTERS or NO_FIREWALL_INTERFACE. Nothing is half applied.
- **Prototype.** The Configlet writes `static` and `policy-forwarding` in the
  VRF, so a VRF that also uses Default Route FabricStatic is not supported.
  The production path is the Push Pull Provider in EDA 26.12.

## If the PAN UI is slow

The same tag change through the XML API, with commit and job polling (1 to 3
minutes each):

```bash
bash scripts/fw-watch-pan.sh on     # add eda-watch and commit
bash scripts/fw-watch-check.sh      # report, Configlet, leaf, path, HTTP
bash scripts/fw-watch-pan.sh off    # remove the tag and commit
```

`fw-watch-pan.sh stage` recreates the address, group, tag and rule without
the tag. It is only needed if the rule was deleted.

## Recovery

If a report transaction fails, remove the tag and commit. The report then
derives nothing for steering, and the next transaction clears the failure.
A Rejected report keeps its GroupTags, so the AssociationPolicies keep
working while it is retried.
