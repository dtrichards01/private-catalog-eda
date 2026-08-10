  # EDA Support Automation App

  Install via **App Management** using catalog `private-eda-catalog`.

  ## Features

  - **SupportMonitor** (cluster) — polls active alarms on an interval
  - **AlarmWorkflowRule** (namespace) — map alarm regex → diagnostic workflow
  - **Root-cause hints** — rule-based RCA text per alarm pattern
  - **Workflow triggers** — ping, systemping, routetrace, routelookup, attachmentlookup,
    checkdefaultbgppeers, techsupport, checkinterfaces, islping, edgeping

  ## After install

  1. Create a **SupportMonitor** CR (cluster scope) — enables polling
  2. Optionally create **AlarmWorkflowRule** CRs to override default rules
  3. View workflow runs in EDA Workflow UI

  ## Build image

  ```bash
  cd packages/support.eda.local
  edabuilder build   # if edabuilder available
  docker build -t ghcr.io/dtrichards01/private-eda-registry/support:v1.0.0 .
  docker push ghcr.io/dtrichards01/private-eda-registry/support:v1.0.0
  ```

  ## Client integration

`eda-mcp-client` alarm monitor (`eda-alarm-monitor`) uses the same rule logic locally.
This app runs the automation **on-cluster** inside EDA.
