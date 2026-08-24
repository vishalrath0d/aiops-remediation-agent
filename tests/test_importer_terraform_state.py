import os

from agent.importer.terraform_state import import_from_file

_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "terraform_show.json")


def test_parses_real_terraform_show_output():
    """This fixture is a REAL `terraform show -json` capture from the
    actually-applied demo_infra/terraform (see the file's own presence --
    generated live, not hand-written), so this test is really asserting
    the parser handles Terraform's real state shape, not a guess at it."""
    resources = import_from_file(_FIXTURE)
    addresses = {r.address for r in resources}
    assert "docker_container.instance" in addresses
    assert "docker_image.instance_base" in addresses

    container = next(r for r in resources if r.address == "docker_container.instance")
    assert container.resource_type == "docker_container"
    assert container.attributes["name"] == "aiops-demo-instance"
