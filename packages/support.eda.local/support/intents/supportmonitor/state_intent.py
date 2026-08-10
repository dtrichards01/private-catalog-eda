"""State intent: poll active alarms and trigger diagnostic workflows.

Uses support.lib.monitor_runner when running inside the EDA app runtime.
Integrates with WorkflowDefinition CRs on the cluster (ping, routetrace, etc.).
"""

import logging

logger = logging.getLogger("support.supportmonitor")

def handle(event, context):
    # Runtime hooks provided by EDA app engine:
    #   context.fetch_alarms() -> list[dict]
    #   context.start_workflow(kind, args) -> dict
    fetch = getattr(context, "fetch_alarms", None)
    start_wf = getattr(context, "start_workflow", None)
    if not fetch or not start_wf:
        logger.warning("Support monitor runtime hooks not available in this context")
        return {"skipped": True}
    from support.lib.monitor_runner import MonitorSettings, run_poll_cycle
    from support.lib.mappings import DEFAULT_ALARM_WORKFLOW_RULES, AlarmWorkflowRule
    from support.lib.state import TriggerStore

    obj = event.get("object") or {}
    spec = obj.get("spec") or {}
    settings = MonitorSettings(
        poll_interval_seconds=int(spec.get("pollIntervalSeconds") or 60),
        cooldown_seconds=int(spec.get("cooldownSeconds") or 300),
        dry_run=bool(spec.get("dryRun", False)),
        enabled=bool(spec.get("enabled", True)),
        rules=list(DEFAULT_ALARM_WORKFLOW_RULES),
    )

    def trigger_fn(alarm, workflow, wf_args):
        if settings.dry_run:
            return {"ok": True, "dry_run": True, "workflow": workflow, "args": wf_args}
        return start_wf(workflow, wf_args)

    result = run_poll_cycle(
        fetch(),
        settings,
        trigger_fn=trigger_fn,
        store=TriggerStore(),
    )
    return {
        "alarmsSeen": result.alarms_seen,
        "triggered": len(result.triggered),
        "errors": result.errors,
        "rca": result.rca,
    }
