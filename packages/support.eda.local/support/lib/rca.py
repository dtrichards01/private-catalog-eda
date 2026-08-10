"""Rule-based root-cause hints from alarm context."""

from __future__ import annotations

import re
from typing import Any


RCA_HINTS: list[tuple[str, str]] = [
    (r"BGP.*(Down|Session|Peer)", "BGP session down — check default BGP peers, underlay reachability, and peer oper-state."),
    (r"Interface.*(Down|Oper)", "Interface oper-down — run checkinterfaces; verify LLDP/ISL and physical link."),
    (r".*ISL.*", "ISL alarm — run islping between fabric nodes; verify topo links and interface state."),
    (r".*Route.*(Trace|Unreachable)", "Routing reachability — run routetrace/routelookup for the affected prefix."),
    (r".*Attachment.*", "Service attachment issue — run attachmentlookup for the VPRN/VNET context."),
    (r".*Ping.*|.*Reachability.*", "Reachability failure — run ping or systemping on the affected node."),
    (r".*TechSupport.*", "Collect techsupport bundle from the affected node for deeper analysis."),
]


def suggest_root_cause(alarm: dict[str, Any]) -> list[str]:
    name = str(alarm.get("name") or alarm.get("alarmName") or "")
    resource = str(alarm.get("resource") or "")
    hints: list[str] = []
    for pattern, text in RCA_HINTS:
        if re.search(pattern, name, re.I) or re.search(pattern, resource, re.I):
            hints.append(text)
    if not hints:
        hints.append(
            f"Review alarm '{name}' on resource '{resource}' and match to a diagnostic workflow."
        )
    return hints
