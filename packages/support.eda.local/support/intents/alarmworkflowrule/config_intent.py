"""Config intent for AlarmWorkflowRule — validates rule and logs match preview."""

def handle(event, context):
    obj = event.get("object") or {}
    spec = obj.get("spec") or {}
    pattern = spec.get("alarmPattern") or ""
    workflow = spec.get("workflow") or ""
    if not pattern or not workflow:
        raise ValueError("alarmPattern and workflow are required")
    return {"ok": True, "workflow": workflow, "pattern": pattern}
