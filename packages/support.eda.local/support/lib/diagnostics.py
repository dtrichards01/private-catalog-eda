"""Diagnostic workflow catalog and name resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import re


@dataclass(frozen=True)
class DiagnosticWorkflow:
    key: str
    kind: str
    title: str
    aliases: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    description: str = ""


DIAGNOSTIC_WORKFLOWS: dict[str, DiagnosticWorkflow] = {
    "edgeping": DiagnosticWorkflow(
        key="edgeping", kind="EdgePing", title="Edge Ping",
        aliases=("edge-ping", "edge_ping"),
        required_inputs=("namespace", "node"), optional_inputs=("fabric", "name"),
        description="Ping from edge toward a remote target.",
    ),
    "systemping": DiagnosticWorkflow(
        key="systemping", kind="SystemPing", title="System Ping",
        aliases=("system-ping", "system_ping"),
        required_inputs=("namespace", "node"), optional_inputs=("name",),
        description="System-level reachability ping on a node.",
    ),
    "routetrace": DiagnosticWorkflow(
        key="routetrace", kind="RouteTrace", title="Route Trace",
        aliases=("route-trace", "route_trace"),
        required_inputs=("namespace", "node"), optional_inputs=("prefix", "name"),
        description="Trace route to a destination prefix.",
    ),
    "routelookup": DiagnosticWorkflow(
        key="routelookup", kind="RouteLookup", title="Route Lookup",
        aliases=("route-lookup", "route_lookup"),
        required_inputs=("namespace", "node"), optional_inputs=("prefix", "name"),
        description="Lookup route for a prefix on a node.",
    ),
    "attachmentlookup": DiagnosticWorkflow(
        key="attachmentlookup", kind="AttachmentLookup", title="Attachment Lookup",
        aliases=("attachment-lookup", "attachment_lookup"),
        required_inputs=("namespace",), optional_inputs=("node", "fabric", "name"),
        description="Lookup service attachment state.",
    ),
    "checkdefaultbgppeers": DiagnosticWorkflow(
        key="checkdefaultbgppeers", kind="CheckDefaultBgpPeers", title="Check BGP",
        aliases=("check-bgp", "checkbgp", "check_default_bgp_peers"),
        required_inputs=("namespace",), optional_inputs=("fabric", "node", "name"),
        description="Validate default BGP peer health.",
    ),
    "techsupport": DiagnosticWorkflow(
        key="techsupport", kind="TechSupport", title="Tech Support",
        aliases=("tech-support", "tech_support"),
        required_inputs=("namespace", "node"), optional_inputs=("name",),
        description="Collect tech-support bundle from a node.",
    ),
    "ping": DiagnosticWorkflow(
        key="ping", kind="Ping", title="Ping", aliases=("oam-ping",),
        required_inputs=("namespace",), optional_inputs=("node", "fabric", "name"),
        description="OAM ping workflow.",
    ),
    "checkinterfaces": DiagnosticWorkflow(
        key="checkinterfaces", kind="CheckInterfaces", title="Check Interfaces",
        aliases=("check-interfaces", "check_interfaces"),
        required_inputs=("namespace",), optional_inputs=("node", "fabric", "name"),
        description="Check interface operational state.",
    ),
    "islping": DiagnosticWorkflow(
        key="islping", kind="IslPing", title="ISL Ping",
        aliases=("isl-ping", "isl_ping"),
        required_inputs=("namespace", "fabric"), optional_inputs=("node", "name"),
        description="Ping across inter-switch links in a fabric.",
    ),
}


def _normalize_key(name: str) -> str:
    return (name or "").strip().lower().replace("-", "").replace("_", "")


def list_diagnostic_workflows() -> list[dict[str, Any]]:
    return [
        {
            "key": wf.key,
            "kind": wf.kind,
            "title": wf.title,
            "aliases": list(wf.aliases),
            "required_inputs": list(wf.required_inputs),
            "optional_inputs": list(wf.optional_inputs),
            "description": wf.description,
        }
        for wf in DIAGNOSTIC_WORKFLOWS.values()
    ]


def resolve_diagnostic_key(name: str) -> str | None:
    key = _normalize_key(name)
    if not key:
        return None
    matches: list[str] = []
    for wf in DIAGNOSTIC_WORKFLOWS.values():
        candidates = {wf.key, wf.kind.lower(), *wf.aliases}
        norm = {_normalize_key(c) for c in candidates}
        if key in norm:
            matches.append(wf.key)
    if matches:
        return sorted(matches, key=lambda k: len(k), reverse=True)[0]
    return None


def get_diagnostic_workflow(name: str) -> DiagnosticWorkflow | None:
    resolved = resolve_diagnostic_key(name)
    return DIAGNOSTIC_WORKFLOWS.get(resolved) if resolved else None


def _meta_name(row: dict[str, Any]) -> str:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    return str(row.get("name") or meta.get("name") or "")


def _flow(row: dict[str, Any]) -> dict[str, Any]:
    spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
    flow = spec.get("flowDefinitionResource")
    return flow if isinstance(flow, dict) else {}


def index_workflow_definitions(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map lowercase keys (run name, kind, slug) -> WorkflowDefinition row."""
    kind_titles = {wf.kind: wf.title for wf in DIAGNOSTIC_WORKFLOWS.values()}
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _meta_name(row)
        if name:
            index[name.lower()] = row
        flow = _flow(row)
        kind = str(flow.get("kind") or "")
        if kind:
            index[kind.lower()] = row
            title = kind_titles.get(kind, "")
            if title:
                index[re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")] = row
        parts = name.split("-")
        if len(parts) >= 2:
            index[parts[-2].lower()] = row
    return index


def resolve_workflow_definition_name(name: str, rows: list[dict[str, Any]]) -> str | None:
    """Resolve user input to WorkflowDefinition metadata.name (local stub)."""
    key = (name or "").strip().lower()
    if not key:
        return None
    index = index_workflow_definitions(rows)
    if key in index:
        return _meta_name(index[key])
    for k, row in index.items():
        if key in k or k in key:
            return _meta_name(row)
    return None


def resolve_diagnostic_definition_name(
    workflow_key: str,
    definition_rows: list[dict[str, Any]],
) -> str | None:
    wf = get_diagnostic_workflow(workflow_key)
    if not wf:
        return resolve_workflow_definition_name(workflow_key, definition_rows)
    want_kind = wf.kind.lower()
    for row in definition_rows:
        if not isinstance(row, dict):
            continue
        spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
        flow = spec.get("flowDefinitionResource") if isinstance(spec.get("flowDefinitionResource"), dict) else {}
        kind = str(flow.get("kind") or "").lower()
        if kind == want_kind:
            meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            name = str(row.get("name") or meta.get("name") or "").strip()
            if name:
                return name
    for candidate in (wf.kind, wf.key, *wf.aliases):
        resolved = resolve_workflow_definition_name(candidate, definition_rows)
        if resolved:
            return resolved
    return None


def validate_workflow_args(workflow_key: str, args: dict[str, Any]) -> list[str]:
    resolved = resolve_diagnostic_key(workflow_key) or workflow_key
    wf = DIAGNOSTIC_WORKFLOWS.get(resolved)
    if not wf:
        return []
    return [field for field in wf.required_inputs if not str(args.get(field) or "").strip()]
