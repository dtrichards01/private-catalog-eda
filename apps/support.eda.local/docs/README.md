# EDA Support Automation

Alarm-driven diagnostic automation for Nokia EDA. Polls active alarms, suggests root-cause hints, and triggers diagnostic workflows (ping, routetrace, checkdefaultbgppeers, islping, techsupport, and more).

## Components

- **SupportMonitor** (cluster) — polls active alarms on an interval
- **AlarmWorkflowRule** (namespace) — map alarm regex to diagnostic workflow

## After install

1. Create a **SupportMonitor** CR (cluster scope) to enable polling
2. Optionally create **AlarmWorkflowRule** CRs to override default rules
3. View workflow runs in the EDA Workflow UI
