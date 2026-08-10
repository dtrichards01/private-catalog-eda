"""Alarm poll + workflow trigger runner (EDA app operator)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    from lib.mappings import (
        build_workflow_args_for_alarm,
        match_alarm_to_rules,
        normalize_alarm,
    )
    from lib.rca import suggest_root_cause
    from lib.state import TriggerStore
except ImportError:
    from support.lib.mappings import (
        build_workflow_args_for_alarm,
        match_alarm_to_rules,
        normalize_alarm,
    )
    from support.lib.rca import suggest_root_cause
    from support.lib.state import TriggerStore

logger = logging.getLogger("support.monitor")


@dataclass
class MonitorSettings:
    poll_interval_seconds: int = 60
    cooldown_seconds: int = 300
    dry_run: bool = False
    enabled: bool = True
    rules: list = field(default_factory=list)


@dataclass
class MonitorResult:
    alarms_seen: int = 0
    triggered: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rca: list[dict[str, Any]] = field(default_factory=list)


def run_poll_cycle(
    alarms_raw: list[dict[str, Any]],
    settings: MonitorSettings,
    *,
    trigger_fn: Callable[[dict[str, Any], str, dict[str, Any]], dict[str, Any]],
    store: TriggerStore | None = None,
) -> MonitorResult:
    result = MonitorResult()
    if not settings.enabled:
        return result
    store = store or TriggerStore()
    alarms = [normalize_alarm(a) for a in alarms_raw]
    result.alarms_seen = len(alarms)
    for alarm in alarms:
        result.rca.append({
            "alarm": alarm.get("name"),
            "hints": suggest_root_cause(alarm),
        })
        for rule in match_alarm_to_rules(alarm, settings.rules):
            wf = rule.workflow
            alarm_id = str(alarm.get("name") or alarm.get("alarm_id") or "")
            namespace = str(alarm.get("namespace") or "")
            if store.is_in_cooldown(
                alarm_id,
                wf,
                namespace=namespace,
                cooldown_seconds=settings.cooldown_seconds,
            ):
                continue
            wf_args = build_workflow_args_for_alarm(alarm, rule)
            if settings.dry_run:
                out = {"ok": True, "dry_run": True, "workflow": wf, "args": wf_args}
            else:
                out = trigger_fn(alarm, wf, wf_args)
            success = bool(out.get("ok"))
            store.record_trigger(
                alarm_id=alarm_id,
                workflow=wf,
                namespace=namespace,
                workflow_definition=str(out.get("workflow_definition") or ""),
                success=success,
                transaction_id=out.get("transaction_id"),
                error=str(out["error"]) if out.get("error") else None,
                alarm_snapshot=alarm,
            )
            result.triggered.append(out)
            if out.get("error"):
                result.errors.append(str(out["error"]))
    return result


def sleep_until_next(poll_interval_seconds: int) -> None:
    time.sleep(max(10, poll_interval_seconds))
