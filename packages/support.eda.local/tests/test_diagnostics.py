import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support"))

from lib.diagnostics import (
    resolve_diagnostic_definition_name,
    resolve_diagnostic_key,
    resolve_workflow_definition_name,
)

SAMPLE_DEFINITIONS = [
    {
        "name": "oam-ping-gvk",
        "metadata": {"name": "oam-ping-gvk"},
        "spec": {
            "flowDefinitionResource": {
                "group": "workflows.eda.nokia.com",
                "version": "v1",
                "kind": "Ping",
            }
        },
    },
    {
        "name": "fabrics-islping",
        "metadata": {"name": "fabrics-islping"},
        "spec": {
            "flowDefinitionResource": {
                "group": "workflows.eda.nokia.com",
                "version": "v1",
                "kind": "IslPing",
            }
        },
    },
]


def test_resolve_diagnostic_key_aliases():
    assert resolve_diagnostic_key("check-bgp") == "checkdefaultbgppeers"
    assert resolve_diagnostic_key("IslPing") == "islping"


def test_resolve_workflow_definition_name_stub():
    assert resolve_workflow_definition_name("Ping", SAMPLE_DEFINITIONS) == "oam-ping-gvk"
    assert resolve_workflow_definition_name("isl-ping", SAMPLE_DEFINITIONS) == "fabrics-islping"


def test_resolve_diagnostic_definition_name_by_kind():
    assert (
        resolve_diagnostic_definition_name("ping", SAMPLE_DEFINITIONS)
        == "oam-ping-gvk"
    )
    assert (
        resolve_diagnostic_definition_name("islping", SAMPLE_DEFINITIONS)
        == "fabrics-islping"
    )
