import os

from agent.importer.ansible_inventory import import_inventory

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "inventory.yml")


def test_parses_nested_groups():
    hosts = import_inventory(_FIXTURE)
    names = {h.name for h in hosts}
    assert names == {"aiops-demo-instance", "another-host"}


def test_captures_host_variables():
    hosts = {h.name: h for h in import_inventory(_FIXTURE)}
    assert hosts["another-host"].variables["some_var"] == 1
    assert hosts["aiops-demo-instance"].variables["ansible_connection"] == "community.docker.docker"
