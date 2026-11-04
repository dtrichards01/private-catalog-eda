# Hybrid WATCH demo: firewall rules, fabric microsegmentation and per-host inspection

A step-by-step guide for `firewall.eda.labs` v1.8.9 on EDA #2, namespace
`clab-srl-leaf-spine-dcgw`. It starts from an empty Palo Alto rule base.
Each layer is added on top of the last, and the lab is reset at the end so
the demo can be run again.

| Layer | Where | What it adds |
|-------|-------|--------------|
| 1 | Palo Alto | Address groups, a service and three rules tagged `eda-export-to-gbp` |
| 2 | EDA | AssociationPolicies: where each GroupTag attaches in the fabric |
| 3 | Data path | The fabric enforces the firewall's rules at the leaf |
| 4 | Palo Alto | A dynamic address group and a watch rule tagged `eda-watch` |
| 5 | Palo Alto runtime | Tag one workload IP; EDA steers only that IP through the firewall |
| 6 | Data path | The watched IP is inspected by the PAN, its neighbour is not |
| 7 | Reset | Untag, then return to the baseline with one script |

Allow about 45 minutes with explanations. Most of the time is spent waiting
for Palo Alto commits, which take 1 to 3 minutes each on this lab PAN.

This is a lab prototype. The product path is the Push Pull Provider in EDA
26.12.

## What is already built

The demo does not create these; talk through them as the starting point.

| Piece | State | What it gives the demo |
|-------|-------|------------------------|
| Firewall `palo-alto` | Up, Health 100, Policy Report Enabled, Policy Generation Enabled | The collector reads the PAN's committed policy through the XML API every 30 seconds and EDA may build fabric policy from it |
| Firewall Interfaces `palo-alto-inside`, `palo-alto-outside` | Config State Verified, Default Route None | The PAN's NICs are /30 transit links into the fabric with eBGP to the leaf |
| VNETs `fw-pan-inside`, `fw-pan-outside` | Up | Two VRFs that share no routes, so inside to outside has to cross the PAN |
| Firewall Policy Report `palo-alto` | Health OK, Exported 0, Steered 0 | The collector's view of the PAN policy and what EDA derives from it. There is one report per Firewall and no Create button |

The lab layout:

### Who's who: the test hosts

RED, BLUE and host2 are names of **groups** (PAN address groups, and EDA
GroupTags of the same name). Each group stands for a subnet, and one test
container sits in each subnet:

| Group | Subnet and attachment | Container | Test IPs | Role in the demo |
|-------|-----------------------|-----------|----------|------------------|
| RED (`eda-red`) | 10.31.1.0/24, IRB on srl-leaf-1, VNET and VLAN `fw-pan-inside` | `fw-client-pan-inside` | **10.31.1.10**, the workload that gets watched; **10.31.1.11**, its neighbour, never watched | The client. Every test starts here |
| host2 (`eda-host2`) | 10.31.13.0/30, routed on srl-leaf-1 `ethernet-1/32` (RoutedInterface `fw-pan-inside-host2`), same VRF as RED | `fw-client-pan-inside-2` | **10.31.13.2**, nginx on port 80, no SSH server | The server RED talks to inside the VRF |
| BLUE (`eda-blue`) | 10.31.2.0/24, VNET and VLAN `fw-pan-outside` | `fw-client-pan-outside` | **10.31.2.10**, nginx on port 80 | A server on the other side of the PAN |

Both RED IPs are on the same container and interface (`eth1`); 10.31.1.11
is a secondary address that `baseline` adds. That is how the demo shows one
IP steered to the firewall while its neighbour in the same subnet, VLAN and
GroupTag is not. Each test picks the source address with `--interface`, `-s`
or `-I`.

**They are not in the containerlab topology view.** The three containers
are plain Docker containers on k0r4, wired to srl-leaf-1 and srl-leaf-4
with `containerlab tools veth`, so they carry no containerlab labels.
`client-2`, `client-2-site-1` and the other `client-*` nodes in the clab
view belong to the DCI lab, and the demo never uses them. To reach a demo
host, open a shell on k0r4 (nokia@100.124.186.51):

```bash
docker exec -it fw-client-pan-inside bash      # RED: 10.31.1.10 and 10.31.1.11
docker exec -it fw-client-pan-inside-2 bash    # host2: 10.31.13.2
docker exec -it fw-client-pan-outside bash     # BLUE: 10.31.2.10
```

Firewall side:

| Item | Value |
|------|-------|
| PAN inside | ethernet1/1, zone `inside`, 10.31.11.2 |
| PAN outside | ethernet1/2, zone `outside` |
| PAN rules at baseline | `lab-untagged`, `allow-all` |

```
   RED 10.31.1.10 / .11 ──┐                         ┌── PAN inside 10.31.11.2 ── PAN ── outside ── BLUE 10.31.2.10
   (fw-client-pan-inside) │ srl-leaf-1               │                                    (fw-client-pan-outside)
                          ├── VRF fw-pan-inside-vrf ─┘
   host2 10.31.13.2 ──────┘
   (fw-client-pan-inside-2)
```

RED and host2 are in the same VRF on the same leaf, so the fabric routes
between them directly and the PAN never sees that traffic. That is the case
WATCH is for: the watched IP is sent up to the PAN and back.

## How to drive it

Every step has a **UI** path for the audience and a **script** that does the
same thing through the PAN XML API and kubectl. Run the scripts from WSL in
the repo root:

```bash
bash scripts/fw-demo.sh <mode> [ip]
```

| Mode | Step |
|------|------|
| `baseline` | Reset to the start (step 0 and step 9) |
| `rules` | Layer 1, PAN rules |
| `associate` | Layer 2, AssociationPolicies |
| `test` | Data path from both RED IPs, PAN sessions, leaf policy routing |
| `watch-rule` | Layer 4, dynamic group and watch rule |
| `tag 10.31.1.10` | Layer 5, put the IP under watch (no commit) |
| `watch-allow` | Optional guard demo |
| `untag 10.31.1.10` | Release the IP |
| `report` | Print the report as EDA has it |
| `all` | Every step in order, ending at baseline |

The script reads the PAN credentials from the `palo-alto-admin` Secret, never
prints them, and waits for EDA to commit each change before it returns.

To watch EDA during the demo, keep these open:

- **Firewall Policy Reports**, report `palo-alto`: Summary, Groups, Rules and
  Derived (Policy and Steering).
- **Microsegmentation**, policy `fw-palo-alto` (exists from layer 2).
- A shell on k0r4 for the leaf:

  ```bash
  docker exec "$(docker ps --format '{{.Names}}' | grep 'srl-leaf-1$')" sr_cli -d \
    "info from running network-instance fw-pan-inside-vrf policy-forwarding"
  ```

## Step 0. Confirm the baseline (2 min)

```bash
bash scripts/fw-demo.sh baseline
```

Expected end of the output:

```
  PAN rules left: lab-untagged, allow-all
  report: health OK, config version NN, generation Enabled, exported 0, steered 0
  EDA status: generation Enabled, groupTags 0, translated 0, policy -, steered 0, committed yes
  srl-leaf-1 policy-forwarding: none
```

`baseline` also makes sure the test hosts are ready: it adds 10.31.1.11 to
`fw-client-pan-inside` and starts nginx on host2 and BLUE.

Run `test` once now to set the reference. Without any policy every flow
works, and SSH to host2 is **refused by host** (host2 answers with a reset;
no SSH server runs there). That matters in layer 3, where the same probe
becomes **dropped**.

```
  10.31.1.10 -> host2 10.31.13.2: http 200, ssh refused by host, ping 0% loss
  10.31.1.11 -> host2 10.31.13.2: http 200, ssh refused by host, ping 0% loss
  10.31.1.10 -> BLUE 10.31.2.10: http 200, ping 0% loss (through the PAN, inside to outside)
```

## Step 1. Layer the firewall rules on the PAN (6 min)

**Message:** the security team writes policy once, on the firewall. A tag on
the rule says "the fabric should enforce this too".

In the PAN web UI (https://100.124.186.51:8444), vsys1:

1. **Objects, Tags.** Add `eda-export-to-gbp`.
2. **Objects, Addresses.** Add:

   | Name | Type | Value |
   |------|------|-------|
   | `eda-red-subnet` | IP Netmask | 10.31.1.0/24 |
   | `eda-blue-subnet` | IP Netmask | 10.31.2.0/24 |
   | `eda-host2-subnet` | IP Netmask | 10.31.13.0/30 |

3. **Objects, Address Groups.** Add three static groups, one member each:
   `eda-red` (`eda-red-subnet`), `eda-blue` (`eda-blue-subnet`), `eda-host2`
   (`eda-host2-subnet`). Group names must be lower case: EDA derives a
   GroupTag of the same name from each.
4. **Objects, Services.** Add `eda-tcp-web`, TCP, destination ports `80,443`,
   and `eda-tcp-ssh`, TCP, destination port `22`.
5. **Policies, Security.** Add three rules, each with tag `eda-export-to-gbp`,
   application any, and Log at Session End. Move them above `lab-untagged`:

   | Name | From | To | Source | Destination | Service | Action |
   |------|------|----|--------|-------------|---------|--------|
   | `EDA-RED-to-BLUE-WEB` | inside | outside | `eda-red` | `eda-blue` | `eda-tcp-web` | Allow |
   | `EDA-RED-to-HOST2-WEB` | inside | inside | `eda-red` | `eda-host2` | `eda-tcp-web` | Allow |
   | `EDA-RED-to-HOST2-SSH` | inside | inside | `eda-red` | `eda-host2` | `eda-tcp-ssh` | Deny |

6. **Commit.**

Script: `bash scripts/fw-demo.sh rules`.

**What EDA shows** within about 30 seconds of the commit finishing, on
report `palo-alto`:

- the new Firewall Config Version, and Exported 3;
- Groups `eda-red`, `eda-blue`, `eda-host2`, each **UNRESOLVED** with
  `GROUPTAG_NOT_ASSOCIATED`. EDA created the GroupTags but they are not
  attached to anything yet;
- Translated 0. No fabric policy exists yet.

**Why the deny is SSH only.** A natural first try is "allow web, then deny
everything else" between RED and host2. EDA refuses that rule with
`PRECEDENCE_AMBIGUOUS: EDA-RED-to-HOST2-WEB`. Fabric group-based policy has
no rule order: an Accept for port 80 and a Drop for everything would both
match port 80, and the leaf would not know which one wins. EDA only
translates rules whose meaning survives without order, so the deny names
the service it blocks. This is also why the fabric has no "default deny"
here: GBP has no implicit deny, and traffic that no entry matches is
forwarded.

## Step 2. Attach the GroupTags in the fabric (4 min)

**Message:** the firewall says *what* is allowed; the operator says *where*
each group lives in the fabric. EDA never guesses attachments from IPs.

In the EDA UI, **Microsegmentation, Association Policies**, create three
policies in namespace `clab-srl-leaf-spine-dcgw`:

| Name | GroupTag | Target |
|------|----------|--------|
| `eda-red` | `eda-red` | VLAN `fw-pan-inside` |
| `eda-blue` | `eda-blue` | VLAN `fw-pan-outside` |
| `eda-host2` | `eda-host2` | Routed interface `fw-pan-inside-host2` |

The same YAML is in
[`examples/08-demo-associations.yaml`](../examples/08-demo-associations.yaml).

Script: `bash scripts/fw-demo.sh associate`.

**What EDA shows** in 1 to 2 minutes:

- the three groups turn **RESOLVED** and Translated becomes 3;
- Derived, Policy lists five entries, now in the read-only
  MicroSegmentationPolicy **`fw-palo-alto`**:

  ```
  EDA-RED-to-BLUE-WEB    eda-red -> eda-blue  TCP 80  Accept
  EDA-RED-to-BLUE-WEB    eda-red -> eda-blue  TCP 443 Accept
  EDA-RED-to-HOST2-WEB   eda-red -> eda-host2 TCP 80  Accept
  EDA-RED-to-HOST2-WEB   eda-red -> eda-host2 TCP 443 Accept
  EDA-RED-to-HOST2-SSH   eda-red -> eda-host2 TCP 22  Drop
  ```

Open `fw-palo-alto` and show that it cannot be edited: the report owns it,
and the next PAN change rewrites it.

## Step 3. Test the data path: the fabric enforces the firewall's policy (3 min)

**Message:** the leaf now applies the security team's rules next to the
workload, for traffic the firewall never sees.

```bash
bash scripts/fw-demo.sh test
```

```
  10.31.1.10 -> host2 10.31.13.2: http 200, ssh dropped, ping 0% loss
  10.31.1.11 -> host2 10.31.13.2: http 200, ssh dropped, ping 0% loss
  10.31.1.10 -> BLUE 10.31.2.10: http 200, ping 0% loss (through the PAN, inside to outside)
  PAN sessions to host2: none
  srl-leaf-1 policy-forwarding: none
```

| Flow | Result | Enforced by |
|------|--------|-------------|
| RED to host2, HTTP | 200 | Fabric Accept on srl-leaf-1; routed directly in the VRF |
| RED to host2, SSH | dropped (was refused at baseline) | Fabric Drop on srl-leaf-1, from `EDA-RED-to-HOST2-SSH` |
| RED to host2, ping | works | No entry matches; GBP has no implicit deny |
| RED to BLUE | works | Different VRFs, so it crosses the PAN, which applies its own rules |
| PAN sessions to host2 | none | The PAN never sees RED to host2 |

By hand, from k0r4:

```bash
docker exec fw-client-pan-inside curl -s -o /dev/null -w '%{http_code}\n' --interface 10.31.1.10 http://10.31.13.2/
docker exec fw-client-pan-inside nc -z -w 3 -s 10.31.1.10 10.31.13.2 22; echo $?
docker exec fw-client-pan-inside ping -c 3 -I 10.31.1.10 10.31.13.2
```

The leaf finds the source GroupTag from its MAC table for a local host (or a
longest-prefix lookup) and enforces on the sending leaf.

## Step 4. Arm the watch on the PAN (5 min)

**Message:** now a security event. The SOC wants a suspicious workload's
traffic inspected by the firewall, even to its neighbours in the same VRF.
The firewall rule defines the scope once; which workloads are watched is
decided at runtime.

In the PAN web UI:

1. **Objects, Tags.** Add `eda-watch` (marks a rule EDA should steer) and
   `eda-security-watch` (the runtime tag the SOC puts on an IP).
2. **Objects, Address Groups.** Add `eda-watched`, type **Dynamic**, match
   `'eda-security-watch'`.
3. **Policies, Security.** Add `EDA-WATCH-HOST2`, tag `eda-watch`:

   | From | To | Source | Destination | Application | Service | Action |
   |------|----|--------|-------------|-------------|---------|--------|
   | inside | inside | `eda-watched` | `eda-host2` | any | any | Deny |

   Place it after the three exported rules and above `lab-untagged`.
4. **Commit.**

Script: `bash scripts/fw-demo.sh watch-rule`.

**Read the rule order out loud.** A watched workload's traffic arriving at the
PAN meets the exported rules first: web to host2 is allowed and SSH is
denied, exactly as the fabric would. Everything else hits
`EDA-WATCH-HOST2` and is denied. Under watch, the workload keeps what policy
allows it and loses everything else.

**What EDA shows** within about 30 seconds of the commit:

```
   steer EDA-WATCH-HOST2  ARMED    - -> -
         NO_MEMBERS: dynamic group eda-watched has no members; tag an IP to steer it
```

**ARMED** means the rule is understood and ready, but nobody is watched, so
nothing is steered. The leaf has no policy routing.

## Step 5. Put one workload under watch (3 min)

**Message:** no commit, no change in EDA. One runtime tag on one IP.

In production this call comes from the SOC: a SOAR playbook, a SIEM, or a PAN
Auto-Tag log-forwarding action. In the lab, use the PAN XML API User-ID call:

```bash
# PAN_KEY from: curl -sk -X POST https://100.124.186.51:8444/api/ -d type=keygen --data-urlencode user=... --data-urlencode password=...
curl -sk -X POST https://100.124.186.51:8444/api/ \
  --data-urlencode type=user-id --data-urlencode "key=$PAN_KEY" \
  --data-urlencode 'cmd=<uid-message><version>2.0</version><type>update</type><payload><register><entry ip="10.31.1.10"><tag><member>eda-security-watch</member></tag></entry></register></payload></uid-message>'
```

Script: `bash scripts/fw-demo.sh tag 10.31.1.10`.

Show it in the PAN UI: **Objects, Address Groups**, `eda-watched`, click
**more...** in the Addresses column. It lists 10.31.1.10.

**What EDA shows** in under a minute:

```
   steer EDA-WATCH-HOST2  STEERED  10.31.1.10/32 -> 10.31.13.0/30 via 10.31.11.2
```

- Steered 1. The source is the host, `10.31.1.10/32`, inside its Fabric
  Subnet 10.31.1.0/24. 10.31.1.11 is in the same subnet and is not steered.
- No warnings. The collector checked that the PAN holds the watched traffic
  in line with the fabric policy (see step 7).
- EDA committed derived Configlet `fw-steer-palo-alto-srl-leaf-1` by itself.

On srl-leaf-1:

```
srl-leaf-1 policy-forwarding: fw-steer-ethernet-1-32-4097, fw-steer-irb0-7 (10.31.1.10/32 10.31.13.0/30)
```

- `fw-steer-irb0-7` on RED's IRB matches source 10.31.1.10/32 to
  10.31.13.0/30 and sends it to next-hop group `fw-steer-palo-alto`
  (10.31.11.2).
- `fw-steer-ethernet-1-32-4097` on host2's port matches the return traffic,
  10.31.13.0/30 to 10.31.1.10/32, so the PAN sees both directions of the
  session.

## Step 6. Test the watched data path (4 min)

```bash
bash scripts/fw-demo.sh test
```

```
  10.31.1.10 -> host2 10.31.13.2: http 200, ssh dropped, ping 100% loss
  10.31.1.11 -> host2 10.31.13.2: http 200, ssh dropped, ping 0% loss
  10.31.1.10 -> BLUE 10.31.2.10: http 200, ping 0% loss (through the PAN, inside to outside)
  PAN session 10.31.1.10 -> 10.31.13.2:80 app web-browsing rule EDA-RED-to-HOST2-WEB zone inside -> inside
```

| From | HTTP | SSH | Ping | Path |
|------|------|-----|------|------|
| 10.31.1.10, watched | 200, inspected | dropped by the fabric | **denied by the PAN** | leaf, PAN, leaf, host2 |
| 10.31.1.11, not watched | 200 | dropped by the fabric | works | leaf, host2 |

Walk through each line:

- **HTTP still works for the watched host, and now the PAN sees it.** In the
  PAN UI, **Monitor, Traffic**, filter `( addr.dst in 10.31.13.2 )`: 10.31.1.10
  to 10.31.13.2:80, inside to inside, rule `EDA-RED-to-HOST2-WEB`, App-ID
  `web-browsing`. Threat, URL and file profiles on that rule now apply.
- **Ping is now denied** for 10.31.1.10 only: rule `EDA-WATCH-HOST2`, the deny
  that ends the watch scope.
- **SSH is still dropped by the fabric.** Policy routing happens after the GBP
  check on the leaf, so a watched host never gets more than the fabric
  allows. WATCH is EDA authorisation first, then PAN inspection.
- **The neighbour is untouched.** 10.31.1.11 shares the subnet, the VLAN and
  the GroupTag, and still goes direct.
- **RED to BLUE** already crossed the PAN between VRFs and is unchanged.

## Step 7 (optional). The guard: a watch rule that lets traffic through (6 min)

**Message:** steering a host to the firewall is only safe if the firewall
holds it to the same policy. The collector checks this on every poll.

Change `EDA-WATCH-HOST2` to **Allow** and commit, or run
`bash scripts/fw-demo.sh watch-allow`. The steering row keeps working and
gains a warning:

```
   steer EDA-WATCH-HOST2  STEERED  10.31.1.10/32 -> 10.31.13.0/30 via 10.31.11.2
         WATCH_FALLTHROUGH_ALLOW: rule EDA-WATCH-HOST2 allows all remaining traffic from 10.31.1.10/32 to 10.31.13.0/30
```

The three warnings:

| Warning | Meaning |
|---------|---------|
| `WATCH_FALLTHROUGH_ALLOW` | The first PAN rule that covers all of the watched pair (any application, any service) is an allow |
| `WATCH_NO_DENY` | No PAN rule covers all of the watched pair, so whatever follows decides, for example `allow-all` |
| `WATCH_ALLOW_NOT_IN_FABRIC` | An allow rule before the covering deny overlaps the pair but is not exported to the fabric, so the PAN allows something the fabric policy does not state |

Zones are not part of the check. Put it back to Deny and commit, or run
`bash scripts/fw-demo.sh watch-rule`; the warning clears.

## Step 8. Release the workload (2 min)

The SOC removes the runtime tag, again with no commit:

```bash
curl -sk -X POST https://100.124.186.51:8444/api/ \
  --data-urlencode type=user-id --data-urlencode "key=$PAN_KEY" \
  --data-urlencode 'cmd=<uid-message><version>2.0</version><type>update</type><payload><unregister><entry ip="10.31.1.10"><tag><member>eda-security-watch</member></tag></entry></unregister></payload></uid-message>'
```

Script: `bash scripts/fw-demo.sh untag 10.31.1.10`.

In under a minute the row goes back to **ARMED**, Steered 0, the Configlet
and both leaf policies are removed, and `test` shows 10.31.1.10 back on the
direct path with ping working.

## Step 9. Back to the baseline

```bash
bash scripts/fw-demo.sh baseline
```

About 5 minutes. In order, it:

1. deletes AssociationPolicies `eda-red`, `eda-blue` and `eda-host2`, and waits
   until `fw-palo-alto` has no entries. This has to come first: EDA refuses to
   delete a GroupTag an AssociationPolicy still uses;
2. unregisters every runtime-tagged IP on the PAN;
3. deletes the demo rules, groups, addresses, services and tags (and older
   fixture objects from earlier labs), keeps `lab-untagged` and `allow-all`,
   and commits;
4. waits for Exported 0 and Steered 0, and checks that srl-leaf-1 has no
   policy routing.

The demo can then be run again from step 1. `bash scripts/fw-demo.sh all` runs
every step end to end and finishes at the baseline.

## How the redirection works

1. The collector polls the PAN every 30 seconds through the XML API: the
   committed rule base and objects, plus the runtime dynamic group members
   (`registered-ip` and `dag-runtime`), which change without a commit.
2. For each enabled rule tagged `eda-watch`, it resolves the source and
   destination into prefixes. A static group gives its subnets or hosts; a
   dynamic group gives each registered IP as a `/32`. Each prefix must sit
   inside a fabric subnet (an IRB or routed interface) in the same router
   as the PAN's interface.
3. It writes one row per source and destination pair to the report under
   Derived, Steering, with a state and reasons: **STEERED**, **ARMED** (a
   dynamic group with no members) or **REFUSED**. The rows are part of the
   derived hash, so a tag change is a new EDA transaction.
4. The report's config intent turns STEERED rows into derived Configlet
   `fw-steer-<firewall>-<node>`: a next-hop group to the PAN's interface
   address under `network-instance static`, plus one forwarding policy per
   workload subinterface, matching source and destination prefixes in both
   directions.
5. The PAN routes the inspected traffic back into the same VRF (a hairpin
   inside to inside). The leaf has no policy on the PAN-facing link, so the
   traffic is not steered again.

Why policy routing: the IXR-D2L has no ACL redirect action, and on SR Linux
26.7 a plain next-hop action drops traffic, so a next-hop group is used.

## Limits to say out loud

- **Routed traffic only.** The watched host and its destination must be in
  different subnets on the same router. Traffic inside one subnet is bridged
  in a MAC-VRF, which cannot be policy routed. A watched IP whose destination
  is its own subnet is REFUSED with `SAME_SUBNET`.
- **One router.** Both subnets and a PAN interface must be in the same VRF;
  otherwise the row is REFUSED (`DIFFERENT_ROUTERS`,
  `NO_FIREWALL_INTERFACE`). Inter-VRF traffic already crosses the PAN.
- **Fabric subnets only.** A prefix outside every fabric subnet is REFUSED
  with `NOT_IN_FABRIC_SUBNET`.
- **No order in GBP.** Exported rules must not overlap with a different
  action (`PRECEDENCE_AMBIGUOUS`). Name the service you deny.
- **The GroupTag stops at the firewall.** After the PAN hop the leaf
  classifies the traffic again by its source. Here the source is still RED,
  so the same entries apply.
- **WATCH is inspection, not containment.** The workload keeps what the policy
  allows. Fabric quarantine (QUARANTINED and ISOLATED) is designed but not
  built; see [DEMO.md](DEMO.md), part 7.
- **Prototype mechanism.** The steering is a Configlet. The product path is
  the Push Pull Provider in EDA 26.12.

## Timings seen in the lab

| Step | Time |
|------|------|
| PAN commit, then EDA reflects it | 2 to 4 min |
| AssociationPolicies to policy built | 1 to 2 min |
| Tag or untag an IP to the leaf changing | under 1 min |
| Baseline | about 5 min |

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| A group stays UNRESOLVED `GROUPTAG_NOT_ASSOCIATED` | Its AssociationPolicy is missing or names a different VLAN or interface |
| A rule is UNSUPPORTED `PRECEDENCE_AMBIGUOUS` | An earlier exported rule overlaps it with a different action. Narrow the service |
| A group is `GROUP_NAME_NOT_LOWERCASE` | Rename the PAN group in lower case |
| The steer row is ARMED after tagging | The tag name differs from the dynamic group's match, or the collector has not polled yet (30 s) |
| The steer row is REFUSED | Read its reason; see Limits |
| Report Generation is Rejected | A derived transaction failed. GroupTags are kept, so the fabric policy keeps working. Untag, fix the cause, and the next change retries |
| `baseline` fails deleting a group | An AssociationPolicy still uses its GroupTag; the script deletes them first, so rerun it |
| HTTP from 10.31.1.11 fails | The secondary IP was lost when the container restarted. `baseline` adds it again |
