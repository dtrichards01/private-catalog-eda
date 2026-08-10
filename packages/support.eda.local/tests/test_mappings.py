import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))

from lib.mappings import match_alarm_to_rules, normalize_alarm, DEFAULT_ALARM_WORKFLOW_RULES
from lib.rca import suggest_root_cause


def test_bgp_alarm_matches_checkdefaultbgppeers():
    alarm = normalize_alarm({
        "name": "BGP-Session-Down-peer-1",
        "severity": "critical",
        "resource": "node/leaf-1 fabric/pod-1",
        "cleared": "false",
        "namespace": "eda",
    })
    rules = match_alarm_to_rules(alarm, DEFAULT_ALARM_WORKFLOW_RULES)
    assert any(r.workflow == "checkdefaultbgppeers" for r in rules)


def test_rca_hint_for_bgp():
    hints = suggest_root_cause({"name": "BGP-Session-Down", "resource": "node/leaf-1"})
    assert hints and "BGP" in hints[0]
