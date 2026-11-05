# Hybrid WATCH demo: firewall rules, fabric microsegmentation and per-host inspection

A step-by-step guide for `firewall.eda.labs` v1.9.0 on EDA #2, namespace
`clab-srl-leaf-spine-dcgw`. It starts from an empty Palo Alto rule base.
Each layer is added on top of the last, and the lab is reset at the end so
the demo can be run again.

| Layer | Where | What it adds |
|-------|-------|--------------|
| 1 | Palo Alto | Address groups RED, BLUE, GREEN and four rules tagged `eda-export-to-gbp` |
| 2 | EDA | AssociationPolicies: where each GroupTag attaches in the fabric |
| 3 | Data path | The leaf enforces the firewall's rules between the colours |
| 4 | Palo Alto | A dynamic address group and a watch rule tagged `eda-watch` |
| 5 | Palo Alto runtime | Tag one host's IP; EDA steers only that host through the firewall |
| 6 | Data path | The watched host is inspected by the PAN, its neighbour is not |
| 7 | Reset | Untag, then return to the baseline with one script |

Allow about 45 minutes with explanations. Most of the time is spent waiting
for Palo Alto commits, which take 1 to 4 minutes each on this lab PAN.

This is a lab prototype, not a product. A product needs the Push Pull
Provider first; development work for the FW Integration App is tracked for
sometime in 2027.

## What is already built

The demo does not create these; talk through them as the starting point.

| Piece | State | What it gives the demo |
|-------|-------|------------------------|
| Firewall `palo-alto` | Up, Health 100, Policy Report Enabled, Policy Generation Enabled | The collector reads the PAN's committed policy and runtime tags through the XML API every 30 seconds, and EDA may build fabric policy from it |
| Firewall Interfaces `palo-alto-inside`, `palo-alto-outside` | Config State Verified, Default Route None | The PAN's NICs are /30 transit links into the fabric with eBGP to the leaf: inside 10.31.11.2 on srl-leaf-1, outside on srl-leaf-4 |
| VNET `fw-pan-inside` | Up | One VRF, `fw-pan-inside-vrf`, on srl-leaf-1 with three colour subnets (RED, BLUE, GREEN) and the PAN's inside link |
| VNET `fw-pan-outside` | Up | A second VRF on srl-leaf-4 that shares no routes with the inside, so inside to outside always crosses the PAN |
| Firewall Policy Report `palo-alto` | Health OK, Exported 0, Steered 0 | The collector's view of the PAN policy and what EDA derives from it. There is one report per Firewall and no Create button |

### Who's who: the hosts

RED, BLUE and GREEN are **groups**: Palo Alto address groups and EDA GroupTags
of the same name. Each group is one subnet of VNET `fw-pan-inside`, and the
test hosts sit in those subnets:

| Host | Container | Address | Group and subnet | srl-leaf-1 port | Role |
|------|-----------|---------|------------------|-----------------|------|
| red-1 | `fw-demo-red-1` | 10.31.1.10 | RED 10.31.1.0/24, VLAN `fw-pan-inside` | e1-22 | The workload that gets watched |
| red-2 | `fw-demo-red-2` | 10.31.1.11 | RED | e1-23 | Its neighbour, never watched |
| blue-1 | `fw-demo-blue-1` | 10.31.3.10 | BLUE 10.31.3.0/24, VLAN `fw-pan-blue` | e1-24 | Web server (nginx, port 80) |
| green-1 | `fw-demo-green-1` | 10.31.4.10 | GREEN 10.31.4.0/24, VLAN `fw-pan-green` | e1-25 | Web server (nginx, port 80) |
| outside | `fw-client-pan-outside` | 10.31.2.10 | VNET `fw-pan-outside` | srl-leaf-4 e1-31 | Web server behind the PAN |

```
                      srl-leaf-1, VRF fw-pan-inside-vrf
   red-1   10.31.1.10 ─┐
   red-2   10.31.1.11 ─┴─ RED   10.31.1.1 ┐
   blue-1  10.31.3.10 ─── BLUE  10.31.3.1 ├── routed between colours
   green-1 10.31.4.10 ─── GREEN 10.31.4.1 ┘
                          PAN inside 10.31.11.2 ── Palo Alto ── outside ── srl-leaf-4 ── outside 10.31.2.10
```

- **Colours are separate subnets in one VRF.** Traffic between colours is
  routed on srl-leaf-1, so the leaf can enforce policy on it and, under
  watch, policy-route it to the PAN. Traffic inside one subnet (red-1 to
  red-2) is bridged and can never be steered.
- **red-1 and red-2 share everything** (subnet, VLAN, GroupTag). That is how
  the demo shows one host steered to the firewall and its neighbour not.
- **The outside host is the classic path through the firewall.** It is in
  another VRF, so the PAN sees that traffic whatever the fabric does.

The four colour hosts are the containerlab lab `fw-demo`
(`fw-demo-hosts.clab.yml`), separate from the DCI topology. srl-leaf-1 is an
external container in that lab, so deploying or destroying it only adds or
removes the four cables. From WSL in the repo root:

```bash
bash scripts/fw-demo-hosts.sh status     # state, addresses, gateway ping, ports
bash scripts/fw-demo-hosts.sh deploy     # create or re-cable the hosts
```

To open a shell on a host, on k0r4 (nokia@100.124.186.51):

```bash
docker exec -it fw-demo-red-1 bash
```

### The policy the demo builds

| From | To | Web (80, 443) | SSH (22) | Anything else |
|------|----|---------------|----------|---------------|
| RED | BLUE | allow | deny | not stated |
| BLUE | GREEN | allow | not stated | not stated |
| RED | GREEN | deny | deny | deny |

Fabric group-based policy has **no implicit deny**: traffic that no entry
matches is forwarded. So "not stated" means allowed on the fabric, for
example ping from RED to BLUE.

## How to drive it

Every step has a **UI** path for the audience and a **script** that does the
same thing through the PAN XML API and kubectl. Run the scripts from WSL in
the repo root:

```bash
bash scripts/fw-demo.sh <mode> [ip or host]
```

| Mode | Step |
|------|------|
| `baseline` | Reset to the start (step 0 and step 9) |
| `rules` | Layer 1, PAN rules |
| `associate` | Layer 2, AssociationPolicies |
| `test` | Data path from red-1, red-2 and blue-1, the PAN traffic log, leaf policy routing |
| `watch-rule` | Layer 4, dynamic group and watch rule |
| `tag red-1` | Layer 5, put red-1 under watch (no commit); an IP works too |
| `watch-allow` | Optional guard demo |
| `untag red-1` | Release red-1 |
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
  docker exec srl-leaf-1 sr_cli -d "info from running network-instance fw-pan-inside-vrf policy-forwarding"
  ```

### Run sheet: run the script, then show the UI

The quickest way to present is to let the script do each step, then open the
pages it changed and explain them. The step sections below give the manual
UI clicks if you want to build a layer by hand instead.

| Step | Run | What the script did | Then show |
|------|-----|---------------------|-----------|
| 0 | `fw-demo-hosts.sh status`, `fw-demo.sh baseline`, `fw-demo.sh test` | Checked the hosts, reset the PAN and EDA, tested every flow | EDA report `palo-alto`: Exported 0, Steered 0. Terminal: everything reachable. PAN **Monitor, Traffic**: only traffic to the outside host |
| 1 | `fw-demo.sh rules` | On the PAN: tag `eda-export-to-gbp`, addresses and groups `eda-red`, `eda-blue`, `eda-green`, services `eda-tcp-web` and `eda-tcp-ssh`, the four rules; then a commit | PAN **Policies, Security**: the four tagged rules. EDA report: Exported 4, groups **UNRESOLVED**. EDA **Microsegmentation, GroupTags**: `eda-red`, `eda-blue`, `eda-green`, created by the report. No policy yet |
| 2 | `fw-demo.sh associate` | In EDA: three AssociationPolicies, each GroupTag to its VLAN. This is the operator's part; it is not derived | EDA **Association Policies**: the three. Report: groups **RESOLVED**, Translated 4. **Microsegmentation, Policies**, `fw-palo-alto`: six entries, read-only |
| 3 | `fw-demo.sh test` | Probed web, SSH and ping from red-1, red-2 and blue-1, then read the PAN traffic log | Terminal: SSH to BLUE and everything to GREEN dropped. PAN **Monitor, Traffic**: still only outside traffic, so the leaf did the dropping |
| 4 | `fw-demo.sh watch-rule` | On the PAN: tags `eda-watch` and `eda-security-watch`, dynamic group `eda-watched`, rule `EDA-WATCH-RED`; then a commit | PAN: the rule and the empty dynamic group. EDA report, Derived, Steering: **ARMED**, `NO_MEMBERS` |
| 5 | `fw-demo.sh tag red-1` | Registered 10.31.1.10 with tag `eda-security-watch` through the User-ID API. No commit | PAN **Objects, Address Groups**, `eda-watched`, **more...**: 10.31.1.10. EDA report: two rows **STEERED**. EDA **Configlets**: `fw-steer-palo-alto-srl-leaf-1` |
| 6 | `fw-demo.sh test` | The same probes | Terminal: red-1's ping to BLUE now fails, red-2's works. PAN **Monitor, Traffic**, filter `( addr.src in 10.31.1.10 )`: every red-1 flow to BLUE and GREEN, with the rule that decided it |
| 7 (optional) | `fw-demo.sh watch-allow`, then `fw-demo.sh watch-rule` | Set `EDA-WATCH-RED` to allow and committed, then put it back | EDA report: `WATCH_FALLTHROUGH_ALLOW` on the RED to BLUE row, then cleared |
| 8 | `fw-demo.sh untag red-1` | Unregistered the IP. No commit | EDA report: **ARMED** again, Steered 0; the Configlet is gone |
| 9 | `fw-demo.sh baseline` | Deleted the AssociationPolicies, the PAN demo objects and the rules, committed, and waited for EDA to clear | Report: Exported 0; `fw-palo-alto` and the derived GroupTags are gone |

Steps 1, 4, 7 and 9 each wait for a PAN commit, which takes 1 to 4 minutes.
That is a good time to explain the step. Don't click Commit in the PAN UI
while a script is running.

**PAN UI and the scripts share one candidate config.** Everything here logs
in as `admin`, so a commit from the UI also commits whatever a script has
staged, and the other way round. Don't run a script while you have
uncommitted edits in the UI. Since v1.9.0 the collector never commits
someone else's pending edits on its own; it only commits its own interface
changes, and those carry any pending `admin` edits with them. A dedicated
API account for the Firewall's Secret avoids that.

## Step 0. Confirm the baseline (3 min)

```bash
bash scripts/fw-demo-hosts.sh status
bash scripts/fw-demo.sh baseline
bash scripts/fw-demo.sh test
```

`status` should show the four hosts running, each with 0% loss to its
gateway, and e1-22 to e1-25 up. `baseline` ends with:

```
  PAN rules left: lab-untagged, allow-all
  report: health OK, config version NN, generation Enabled, exported 0, steered 0
  EDA status: generation Enabled, groupTags 0, translated 0, policy -, steered 0, committed yes
  srl-leaf-1 policy-forwarding: none
```

`test` sets the reference. With no policy, every host reaches every other
one, and SSH to blue-1 is **refused by host** (blue-1 answers with a reset;
no SSH server runs there):

```
  red-1   10.31.1.10 -> blue-1  10.31.3.10 http 200, ssh refused by host, ping 0% loss
  red-1   10.31.1.10 -> green-1 10.31.4.10 http 200, ping 0% loss
  red-1   10.31.1.10 -> outside 10.31.2.10 http 200, ping 0% loss
  red-2   10.31.1.11 -> blue-1  10.31.3.10 http 200, ssh refused by host, ping 0% loss
  red-2   10.31.1.11 -> green-1 10.31.4.10 http 200, ping 0% loss
  red-2   10.31.1.11 -> outside 10.31.2.10 http 200, ping 0% loss
  blue-1  10.31.3.10 -> green-1 10.31.4.10 http 200, ping 0% loss
  PAN traffic log from red-1 10.31.1.10:
    -> outside 10.31.2.10    app ping            allow rule allow-all
    -> outside 10.31.2.10:80 app web-browsing    allow rule allow-all
  PAN traffic log from red-2 10.31.1.11:
    -> outside 10.31.2.10    app ping            allow rule allow-all
    -> outside 10.31.2.10:80 app web-browsing    allow rule allow-all
```

**Point at the traffic log.** The PAN only sees the traffic to the outside
host. Everything between the colours stays on srl-leaf-1.

## Step 1. Layer the firewall rules on the PAN (6 min)

**Message:** the security team writes policy once, on the firewall. A tag on
the rule says "the fabric should enforce this too".

In the PAN web UI (https://100.124.186.51:8444), vsys1:

1. **Objects, Tags.** Add `eda-export-to-gbp`.
2. **Objects, Addresses.** Add:

   | Name | Type | Value |
   |------|------|-------|
   | `eda-red-subnet` | IP Netmask | 10.31.1.0/24 |
   | `eda-blue-subnet` | IP Netmask | 10.31.3.0/24 |
   | `eda-green-subnet` | IP Netmask | 10.31.4.0/24 |

3. **Objects, Address Groups.** Add three static groups, one member each:
   `eda-red` (`eda-red-subnet`), `eda-blue` (`eda-blue-subnet`), `eda-green`
   (`eda-green-subnet`). Group names must be lower case: EDA derives a
   GroupTag of the same name from each.
4. **Objects, Services.** Add `eda-tcp-web`, TCP, destination ports `80,443`,
   and `eda-tcp-ssh`, TCP, destination port `22`.
5. **Policies, Security.** Add four rules, each zone `inside` to `inside`,
   tag `eda-export-to-gbp`, application any, and Log at Session End. Move
   them above `lab-untagged`:

   | Name | Source | Destination | Service | Action |
   |------|--------|-------------|---------|--------|
   | `EDA-RED-to-BLUE-WEB` | `eda-red` | `eda-blue` | `eda-tcp-web` | Allow |
   | `EDA-RED-to-BLUE-SSH` | `eda-red` | `eda-blue` | `eda-tcp-ssh` | Deny |
   | `EDA-BLUE-to-GREEN-WEB` | `eda-blue` | `eda-green` | `eda-tcp-web` | Allow |
   | `EDA-RED-to-GREEN-DENY` | `eda-red` | `eda-green` | any | Deny |

6. **Commit.**

Script: `bash scripts/fw-demo.sh rules`.

**What EDA shows** within about 30 seconds of the commit finishing, on
report `palo-alto`:

```
  report: health OK, config version 41, generation Enabled, exported 4, steered 0
   group eda-red    UNRESOLVED   GROUPTAG_NOT_ASSOCIATED: eda-red
   group eda-blue   UNRESOLVED   GROUPTAG_NOT_ASSOCIATED: eda-blue
   group eda-green  UNRESOLVED   GROUPTAG_NOT_ASSOCIATED: eda-green
```

- Exported 4: the four tagged rules. `lab-untagged` and `allow-all` are not
  tagged, so EDA ignores them.
- EDA created GroupTags `eda-red`, `eda-blue` and `eda-green`, but they are
  not attached to anything yet, so each rule waits with
  `GROUPTAG_NOT_ASSOCIATED`. No fabric policy exists yet.

**Why the RED to BLUE deny names a service.** A natural first try is "allow
web, then deny everything else" between RED and BLUE. EDA refuses that rule
with `PRECEDENCE_AMBIGUOUS`. Fabric group-based policy has no rule order: an
Accept for port 80 and a Drop for everything would both match port 80, and
the leaf would not know which wins. EDA only translates rules whose meaning
survives without order. RED to GREEN can be a full deny because nothing else
covers that pair.

## Step 2. Attach the GroupTags in the fabric (4 min)

**Message:** the firewall says *what* is allowed; the operator says *where*
each group lives in the fabric. EDA never guesses attachments from IPs.

In the EDA UI, **Microsegmentation, Association Policies**, create three
policies in namespace `clab-srl-leaf-spine-dcgw`:

| Name | GroupTag | Target VLAN |
|------|----------|-------------|
| `eda-red` | `eda-red` | `fw-pan-inside` |
| `eda-blue` | `eda-blue` | `fw-pan-blue` |
| `eda-green` | `eda-green` | `fw-pan-green` |

The same YAML is in
[`examples/08-demo-associations.yaml`](../examples/08-demo-associations.yaml).

Script: `bash scripts/fw-demo.sh associate`.

**What EDA shows** in about a minute: the groups turn **RESOLVED**,
Translated becomes 4, and Derived, Policy lists six entries, now in the
read-only MicroSegmentationPolicy **`fw-palo-alto`**:

```
   entry EDA-RED-to-BLUE-WEB    eda-red -> eda-blue TCP 80 Accept
   entry EDA-RED-to-BLUE-WEB    eda-red -> eda-blue TCP 443 Accept
   entry EDA-RED-to-BLUE-SSH    eda-red -> eda-blue TCP 22 Drop
   entry EDA-BLUE-to-GREEN-WEB  eda-blue -> eda-green TCP 80 Accept
   entry EDA-BLUE-to-GREEN-WEB  eda-blue -> eda-green TCP 443 Accept
   entry EDA-RED-to-GREEN-DENY  eda-red -> eda-green any  Drop
```

Open `fw-palo-alto` and show that it cannot be edited: the report owns it,
and the next PAN change rewrites it.

## Step 3. Test: the leaf enforces the firewall's policy (3 min)

**Message:** the leaf now applies the security team's rules next to the
workload, for traffic the firewall never sees.

```bash
bash scripts/fw-demo.sh test
```

```
  red-1   10.31.1.10 -> blue-1  10.31.3.10 http 200, ssh dropped, ping 0% loss
  red-1   10.31.1.10 -> green-1 10.31.4.10 http 000, ping 100% loss
  red-1   10.31.1.10 -> outside 10.31.2.10 http 200, ping 0% loss
  red-2   10.31.1.11 -> blue-1  10.31.3.10 http 200, ssh dropped, ping 0% loss
  red-2   10.31.1.11 -> green-1 10.31.4.10 http 000, ping 100% loss
  red-2   10.31.1.11 -> outside 10.31.2.10 http 200, ping 0% loss
  blue-1  10.31.3.10 -> green-1 10.31.4.10 http 200, ping 0% loss
  PAN traffic log from red-1 10.31.1.10:
    -> outside 10.31.2.10    app ping            allow rule allow-all
    -> outside 10.31.2.10:80 app web-browsing    allow rule allow-all
```

| Flow | Result | Enforced by |
|------|--------|-------------|
| RED to BLUE, web | 200 | Fabric Accept on srl-leaf-1, routed directly |
| RED to BLUE, SSH | **dropped** (refused at baseline) | Fabric Drop, from `EDA-RED-to-BLUE-SSH` |
| RED to BLUE, ping | works | No entry matches; no implicit deny |
| RED to GREEN, anything | **dropped** | Fabric Drop, from `EDA-RED-to-GREEN-DENY` |
| BLUE to GREEN, web | 200 | Fabric Accept |
| RED to outside | works, through the PAN | Different VRF; the PAN's `allow-all` |

The PAN traffic log still shows only the outside traffic: every drop above
happened on the leaf, next to the workload.

By hand, from k0r4:

```bash
docker exec fw-demo-red-1 curl -s -o /dev/null -w '%{http_code}\n' http://10.31.3.10/
docker exec fw-demo-red-1 nc -z -w 3 10.31.3.10 22; echo $?
docker exec fw-demo-red-1 ping -c 3 10.31.4.10
```

## Step 4. Arm the watch on the PAN (5 min)

**Message:** now a security event. The SOC wants a suspicious workload's
traffic to its neighbours inspected by the firewall. The rule defines the
scope once; which workloads are watched is decided at runtime.

In the PAN web UI:

1. **Objects, Tags.** Add `eda-watch` (marks a rule EDA should steer) and
   `eda-security-watch` (the runtime tag the SOC puts on an IP).
2. **Objects, Address Groups.** Add `eda-watched`, type **Dynamic**, match
   `'eda-security-watch'`.
3. **Policies, Security.** Add `EDA-WATCH-RED`, tag `eda-watch`:

   | From | To | Source | Destination | Application | Service | Action |
   |------|----|--------|-------------|-------------|---------|--------|
   | inside | inside | `eda-watched` | `eda-blue`, `eda-green` | any | any | Deny |

   Place it after the four exported rules and above `lab-untagged`.
4. **Commit.**

Script: `bash scripts/fw-demo.sh watch-rule`.

**Read the rule order out loud.** A watched workload's traffic arriving at
the PAN meets the exported rules first, so it gets exactly what the policy
allows: web to BLUE yes, SSH to BLUE no, nothing to GREEN. Everything else
falls to `EDA-WATCH-RED` and is denied. Under watch, the workload keeps what
the policy allows and loses the "not stated" traffic, such as ping.

**What EDA shows** within about 30 seconds of the commit:

```
   steer EDA-WATCH-RED  ARMED    - -> -
         NO_MEMBERS: dynamic group eda-watched has no members; tag an IP to steer it
```

**ARMED** means the rule is understood and ready, but nobody is watched, so
nothing is steered. The leaf has no policy routing.

## Step 5. Put red-1 under watch (3 min)

**Message:** no commit, no change in EDA. One runtime tag on one IP.

In production this call comes from the SOC: a SOAR playbook, a SIEM, or a PAN
Auto-Tag log-forwarding action. In the lab, use the PAN XML API User-ID call:

```bash
# PAN_KEY from: curl -sk -X POST https://100.124.186.51:8444/api/ -d type=keygen --data-urlencode user=... --data-urlencode password=...
curl -sk -X POST https://100.124.186.51:8444/api/ \
  --data-urlencode type=user-id --data-urlencode "key=$PAN_KEY" \
  --data-urlencode 'cmd=<uid-message><version>2.0</version><type>update</type><payload><register><entry ip="10.31.1.10"><tag><member>eda-security-watch</member></tag></entry></register></payload></uid-message>'
```

Script: `bash scripts/fw-demo.sh tag red-1`.

Show it in the PAN UI: **Objects, Address Groups**, `eda-watched`, click
**more...** in the Addresses column. It lists 10.31.1.10.

**What EDA shows** in under a minute:

```
  report: ... exported 4, steered 2
   steer EDA-WATCH-RED  STEERED  10.31.1.10/32 -> 10.31.3.0/24 via 10.31.11.2
   steer EDA-WATCH-RED  STEERED  10.31.1.10/32 -> 10.31.4.0/24 via 10.31.11.2
  srl-leaf-1 policy-forwarding: fw-steer-irb0-17, fw-steer-irb0-18, fw-steer-irb0-7 (10.31.1.10/32 10.31.3.0/24 10.31.4.0/24)
```

- Two rows, one per destination group. The source is the host,
  `10.31.1.10/32`, inside its Fabric Subnet 10.31.1.0/24. red-2 is in the
  same subnet and is not steered.
- No warnings: the collector checked that the PAN holds the watched traffic
  to the exported policy (see step 7).
- EDA committed derived Configlet `fw-steer-palo-alto-srl-leaf-1` by itself.
  On srl-leaf-1 it is three forwarding policies: one on RED's IRB for red-1's
  traffic out, and one on each of BLUE's and GREEN's IRBs for the return
  traffic to red-1, so the PAN sees both directions. The IRB numbers
  (`irb0-17`, `irb0-18`) are allocated by EDA and can differ.

## Step 6. Test the watched data path (4 min)

```bash
bash scripts/fw-demo.sh test
```

```
  red-1   10.31.1.10 -> blue-1  10.31.3.10 http 200, ssh dropped, ping 100% loss
  red-1   10.31.1.10 -> green-1 10.31.4.10 http 000, ping 100% loss
  red-1   10.31.1.10 -> outside 10.31.2.10 http 200, ping 0% loss
  red-2   10.31.1.11 -> blue-1  10.31.3.10 http 200, ssh dropped, ping 0% loss
  red-2   10.31.1.11 -> green-1 10.31.4.10 http 000, ping 100% loss
  red-2   10.31.1.11 -> outside 10.31.2.10 http 200, ping 0% loss
  blue-1  10.31.3.10 -> green-1 10.31.4.10 http 200, ping 0% loss
  PAN traffic log from red-1 10.31.1.10:
    -> outside 10.31.2.10    app ping            allow rule allow-all
    -> outside 10.31.2.10:80 app web-browsing    allow rule allow-all
    -> blue-1  10.31.3.10    app ping            deny  rule EDA-WATCH-RED
    -> blue-1  10.31.3.10:22 app not-applicable  deny  rule EDA-RED-to-BLUE-SSH
    -> blue-1  10.31.3.10:80 app web-browsing    allow rule EDA-RED-to-BLUE-WEB
    -> green-1 10.31.4.10    app ping            deny  rule EDA-RED-to-GREEN-DENY
    -> green-1 10.31.4.10:80 app not-applicable  deny  rule EDA-RED-to-GREEN-DENY
  PAN traffic log from red-2 10.31.1.11:
    -> outside 10.31.2.10    app ping            allow rule allow-all
    -> outside 10.31.2.10:80 app web-browsing    allow rule allow-all
```

The same in the PAN UI: **Monitor, Traffic**, filter
`( addr.src in 10.31.1.10 )`.

| From | To BLUE: web | SSH | ping | To GREEN | Who decides |
|------|--------------|-----|------|----------|-------------|
| red-1, watched | 200, **inspected** (App-ID web-browsing) | denied by the PAN | **denied by the PAN** | denied by the PAN | The Palo Alto, every packet |
| red-2, not watched | 200 | dropped by the leaf | works | dropped by the leaf | The leaf, as in step 3 |

Walk through it:

- **The PAN now sees all of red-1's traffic to BLUE and GREEN,** and decides
  it with the same rules the fabric enforces for red-2: web allowed by
  `EDA-RED-to-BLUE-WEB`, SSH denied by `EDA-RED-to-BLUE-SSH`, GREEN denied by
  `EDA-RED-to-GREEN-DENY`. Threat, URL and file profiles on those rules now
  apply to red-1.
- **Ping to BLUE is now denied** for red-1 only, by `EDA-WATCH-RED`, the deny
  that ends the watch scope. The fabric allowed it ("not stated").
- **The neighbour is untouched.** red-2 shares the subnet, VLAN and GroupTag
  and still goes direct; the PAN log shows none of its inside traffic.
- **Steered traffic bypasses the leaf's drops.** The leaf sends red-1's
  packets to the PAN before its group-based Drop entries apply, so for a
  watched host the PAN is the enforcement point. That is why the rule order
  on the PAN matters, and why the collector checks it (step 7).
- **The outside path is unchanged:** it always crossed the PAN.

## Step 7 (optional). The guard: a watch rule that lets traffic through (6 min)

**Message:** steering a host to the firewall is only safe if the firewall
holds it to the same policy. The collector checks this on every poll.

Change `EDA-WATCH-RED` to **Allow** and commit, or run
`bash scripts/fw-demo.sh watch-allow`. The steering keeps working, and the
RED to BLUE row gains a warning:

```
   steer EDA-WATCH-RED  STEERED  10.31.1.10/32 -> 10.31.3.0/24 via 10.31.11.2
         WATCH_FALLTHROUGH_ALLOW: rule EDA-WATCH-RED allows all remaining traffic from 10.31.1.10/32 to 10.31.3.0/24
   steer EDA-WATCH-RED  STEERED  10.31.1.10/32 -> 10.31.4.0/24 via 10.31.11.2
```

The RED to GREEN row has no warning: `EDA-RED-to-GREEN-DENY` comes first and
denies everything there. The three warnings:

| Warning | Meaning |
|---------|---------|
| `WATCH_FALLTHROUGH_ALLOW` | The first PAN rule that covers all of the watched pair (any application, any service) is an allow |
| `WATCH_NO_DENY` | No PAN rule covers all of the watched pair, so whatever follows decides, for example `allow-all` |
| `WATCH_ALLOW_NOT_IN_FABRIC` | An allow rule before the covering deny overlaps the pair but is not exported to the fabric, so the PAN allows something the fabric policy does not state |

Zones are not part of the check. Put it back to Deny and commit, or run
`bash scripts/fw-demo.sh watch-rule`; the warning clears.

## Step 8. Release red-1 (2 min)

The SOC removes the runtime tag, again with no commit:

```bash
curl -sk -X POST https://100.124.186.51:8444/api/ \
  --data-urlencode type=user-id --data-urlencode "key=$PAN_KEY" \
  --data-urlencode 'cmd=<uid-message><version>2.0</version><type>update</type><payload><unregister><entry ip="10.31.1.10"><tag><member>eda-security-watch</member></tag></entry></unregister></payload></uid-message>'
```

Script: `bash scripts/fw-demo.sh untag red-1`.

In under a minute the row goes back to **ARMED**, Steered 0, the Configlet
and the three leaf policies are removed, and `test` shows red-1 back on the
leaf: ping to BLUE works, and the PAN log shows only its outside traffic.

## Step 9. Back to the baseline

```bash
bash scripts/fw-demo.sh baseline
```

About 5 minutes. In order, it:

1. checks the hosts are up and the web servers listen;
2. deletes AssociationPolicies `eda-red`, `eda-blue` and `eda-green`, and
   waits until `fw-palo-alto` has no entries. This has to come first: EDA
   refuses to delete a GroupTag an AssociationPolicy still uses;
3. unregisters every runtime-tagged IP on the PAN;
4. deletes the demo rules, groups, addresses, services and tags (and older
   demo objects), keeps `lab-untagged` and `allow-all`, and commits;
5. waits for Exported 0 and Steered 0, and checks that srl-leaf-1 has no
   policy routing.

The demo can then be run again from step 1. `bash scripts/fw-demo.sh all`
runs every step end to end and finishes at the baseline.

## How the redirection works

1. The collector polls the PAN every 30 seconds through the XML API: the
   committed rule base and objects, plus the runtime dynamic group members
   (`registered-ip` and `dag-runtime`), which change without a commit.
2. For each enabled rule tagged `eda-watch`, it resolves the source and
   destination into prefixes. A static group gives its subnets or hosts; a
   dynamic group gives each registered IP as a `/32`. Each prefix must sit
   inside a fabric subnet (an IRB or routed interface) in the same router as
   the PAN's interface.
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
   traffic is not steered again, and it learns the colour subnets from the
   leaf by eBGP.

Why policy routing: the IXR-D2L has no ACL redirect action, and on SR Linux
26.7 a plain next-hop action drops traffic, so a next-hop group is used.

## Limits to say out loud

- **Routed traffic only.** A watched host's destination must be another
  subnet on the same router. Traffic inside one subnet (red-1 to red-2) is
  bridged in a MAC-VRF, which cannot be policy routed; such a pair is
  REFUSED with `SAME_SUBNET`.
- **One router.** Both subnets and a PAN interface must be in the same VRF;
  otherwise the row is REFUSED (`DIFFERENT_ROUTERS`,
  `NO_FIREWALL_INTERFACE`). Inter-VRF traffic already crosses the PAN.
- **Fabric subnets only.** A prefix outside every fabric subnet is REFUSED
  with `NOT_IN_FABRIC_SUBNET`.
- **No order in GBP, no implicit deny.** Exported rules must not overlap with
  a different action (`PRECEDENCE_AMBIGUOUS`). Name the service you deny.
- **For a watched host, the PAN enforces.** Its steered traffic is not
  dropped by the leaf first, so the PAN must hold it to the same policy. The
  collector warns when it does not; a warning does not stop the steering.
- **WATCH is inspection, not containment.** The workload keeps what the
  policy allows. Fabric quarantine (QUARANTINED and ISOLATED) is designed but
  not built; see [DEMO.md](DEMO.md), part 7.
- **Prototype mechanism.** The steering is a Configlet. The product path is
  the Push Pull Provider, which a product needs first. Development work for the FW
  Integration App is tracked for sometime in 2027.

## Timings seen in the lab

| Step | Time |
|------|------|
| PAN commit, then EDA reflects it | 2 to 5 min |
| AssociationPolicies to policy built | about 1 min |
| Tag or untag an IP to the leaf changing | under 1 min |
| `test` (waits for the PAN traffic log) | about 2 min |
| Baseline | 5 to 8 min |

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `baseline` says hosts not running | Run `bash scripts/fw-demo-hosts.sh deploy`. A host container restart loses its cable; deploy re-creates it |
| A group stays UNRESOLVED `GROUPTAG_NOT_ASSOCIATED` | Its AssociationPolicy is missing or names a different VLAN |
| A rule is UNSUPPORTED `PRECEDENCE_AMBIGUOUS` | An earlier exported rule overlaps it with a different action. Narrow the service |
| A group is `GROUP_NAME_NOT_LOWERCASE` | Rename the PAN group in lower case |
| The steer row is ARMED after tagging | The tag name differs from the dynamic group's match, or the collector has not polled yet (30 s) |
| The steer row is REFUSED | Read its reason; see Limits |
| A UI edit went live before you committed | A script or the collector committed as `admin` at the same time; see "How to drive it" |
| Report Generation is Rejected | A derived transaction failed. GroupTags are kept, so the fabric policy keeps working. Untag, fix the cause, and the next change retries |
| `baseline` fails deleting a group | An AssociationPolicy still uses its GroupTag; the script deletes them first, so rerun it |
| `test` shows no PAN traffic log | The PAN writes logs up to a minute late; the script waits up to two minutes. Rerun `test` |
