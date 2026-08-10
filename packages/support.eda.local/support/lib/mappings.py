"""Alarm-to-workflow mapping rules and matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:
    from lib.diagnostics import resolve_diagnostic_key
except ImportError:
    from support.lib.diagnostics import resolve_diagnostic_key


@dataclass
class AlarmWorkflowRule:
    alarm_pattern: str
    workflow: str
    severity: list[str] = field(default_factory=list)
    resource_pattern: str | None = None
    namespace: str | None = None
    workflow_args: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""

    def __post_init__(self) -> None:
        self._alarm_re = re.compile(self.alarm_pattern, re.IGNORECASE)
        self._resource_re = (
            re.compile(self.resource_pattern, re.IGNORECASE)
            if self.resource_pattern
            else None
        )
        self.workflow = resolve_diagnostic_key(self.workflow) or self.workflow.lower()


DEFAULT_ALARM_WORKFLOW_RULES: list[AlarmWorkflowRule] = [
    AlarmWorkflowRule(
        alarm_pattern=r"BGP.*(Down|Session|Peer)",
        workflow="checkdefaultbgppeers",
        severity=["critical", "major"],
        description="BGP peer/session alarms trigger Check BGP workflow.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r"Interface.*(Down|Oper|State)",
        workflow="checkinterfaces",
        severity=["critical", "major", "warning"],
        description="Interface alarms trigger Check Interfaces workflow.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*ISL.*",
        workflow="islping",
        severity=["critical", "major"],
        description="ISL alarms trigger ISL Ping workflow.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*(Edge|Gateway).*",
        workflow="edgeping",
        severity=["critical", "major"],
        description="Edge/gateway reachability alarms trigger Edge Ping.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*System.*(Ping|Reach)",
        workflow="systemping",
        description="System reachability alarms trigger System Ping.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*Route.*(Trace|Unreachable)",
        workflow="routetrace",
        description="Routing trace alarms trigger Route Trace workflow.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*Route.*(Lookup|Missing|NotFound)",
        workflow="routelookup",
        description="Route lookup alarms trigger Route Lookup workflow.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*Attachment.*",
        workflow="attachmentlookup",
        description="Attachment alarms trigger Attachment Lookup workflow.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*TechSupport.*|.*SupportBundle.*",
        workflow="techsupport",
        severity=["critical", "major"],
        description="Support bundle requests trigger Tech Support workflow.",
    ),
    AlarmWorkflowRule(
        alarm_pattern=r".*Ping.*|.*Reachability.*",
        workflow="ping",
        description="Generic ping/reachability alarms trigger Ping workflow.",
    ),
]


def normalize_alarm(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    namespace = str(
        row.get(".namespace.name")
        or meta.get("namespace")
        or row.get("namespace")
        or ""
    ).strip()
    name = str(row.get("name") or meta.get("name") or row.get("alarm_id") or "").strip()
    severity = str(row.get("severity") or "").strip().lower()
    resource = str(row.get("resource") or row.get("affectedResource") or "").strip()
    description = str(row.get("description") or "").strip()
    cleared = str(row.get("cleared") or "false").strip().lower()
    return {
        "alarm_id": name,
        "name": name,
        "namespace": namespace,
        "severity": severity,
        "resource": resource,
        "description": description,
        "cleared": cleared,
        "raw": row,
    }


_NODE_RE = re.compile(r"(?:node|toponode|leaf|spine|pe|ce)[/-]?([a-zA-Z0-9_.-]+)", re.I)
_FABRIC_RE = re.compile(r"(?:fabric)[/-]?([a-zA-Z0-9_.-]+)", re.I)
_INTERFACE_RE = re.compile(r"(?:interface|if)[/-]?([a-zA-Z0-9_.:/-]+)", re.I)


def extract_workflow_args_from_alarm(alarm: dict[str, Any]) -> dict[str, str]:
    resource = str(alarm.get("resource") or "")
    args: dict[str, str] = {}
    ns = str(alarm.get("namespace") or "").strip()
    if ns:
        args["namespace"] = ns
    node_match = _NODE_RE.search(resource)
    if node_match:
        args["node"] = node_match.group(1)
    fabric_match = _FABRIC_RE.search(resource)
    if fabric_match:
        args["fabric"] = fabric_match.group(1)
    iface_match = _INTERFACE_RE.search(resource)
    if iface_match:
        args["interface"] = iface_match.group(1)
    if not args.get("node") and alarm.get("name"):
        name = str(alarm["name"])
        node_in_name = _NODE_RE.search(name)
        if node_in_name:
            args["node"] = node_in_name.group(1)
    return args


def severity_matches(rule: AlarmWorkflowRule, severity: str) -> bool:
    if not rule.severity:
        return True
    sev = (severity or "").strip().lower()
    return sev in {s.lower() for s in rule.severity}


def match_alarm_to_rules(
    alarm: dict[str, Any],
    rules: list[AlarmWorkflowRule] | None = None,
) -> list[AlarmWorkflowRule]:
    normalized = normalize_alarm(alarm) if "alarm_id" not in alarm else alarm
    active_rules = rules or DEFAULT_ALARM_WORKFLOW_RULES
    if normalized.get("cleared") in ("true", "1", "yes"):
        return []
    matches: list[AlarmWorkflowRule] = []
    alarm_name = str(normalized.get("name") or "")
    resource = str(normalized.get("resource") or "")
    namespace = str(normalized.get("namespace") or "")
    severity = str(normalized.get("severity") or "")
    for rule in active_rules:
        if not rule.enabled:
            continue
        if rule.namespace and rule.namespace != namespace:
            continue
        if not rule._alarm_re.search(alarm_name):
            continue
        if rule._resource_re and not rule._resource_re.search(resource):
            continue
        if not severity_matches(rule, severity):
            continue
        matches.append(rule)
    return matches


def match_alarm_to_workflow(
    alarm: dict[str, Any],
    rules: list[AlarmWorkflowRule] | None = None,
) -> AlarmWorkflowRule | None:
    matches = match_alarm_to_rules(alarm, rules)
    return matches[0] if matches else None


def list_alarm_workflow_mappings(
    rules: list[AlarmWorkflowRule] | None = None,
) -> list[dict[str, Any]]:
    active = rules or DEFAULT_ALARM_WORKFLOW_RULES
    return [
        {
            "alarm_pattern": r.alarm_pattern,
            "workflow": r.workflow,
            "severity": list(r.severity),
            "resource_pattern": r.resource_pattern,
            "namespace": r.namespace,
            "workflow_args": dict(r.workflow_args),
            "enabled": r.enabled,
            "description": r.description,
        }
        for r in active
    ]


def build_workflow_args_for_alarm(
    alarm: dict[str, Any],
    rule: AlarmWorkflowRule,
) -> dict[str, Any]:
    normalized = normalize_alarm(alarm) if "alarm_id" not in alarm else alarm
    args = extract_workflow_args_from_alarm(normalized)
    args.update({k: v for k, v in rule.workflow_args.items() if v is not None})
    return args
