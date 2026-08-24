# The "instance" half of the demo target this project's infra-remediation
# path actually operates on for real: a real, running local Docker
# container, standing in for a real cloud instance (e.g. EC2) without
# needing any cloud credentials. Terraform launches it here; the
# demo_infra/ansible/ playbook configures it afterward -- the same real
# two-tool split (provisioning vs. configuration) the agent's
# responsible-tool routing is built to recognize, just aimed at a local,
# zero-cost, zero-credential target instead of a real cloud account.
#
# Swapping this for a real cloud provider later is a provider-block change
# here, not a rewrite of the agent's remediation engine -- see the root
# README's "Known limitations" section.

terraform {
  required_version = ">= 1.5"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

variable "instance_name" {
  description = "Name of the demo 'instance' container -- also its Ansible inventory hostname."
  type        = string
  default     = "aiops-demo-instance"
}

variable "image" {
  type    = string
  default = "alpine:3.20"
}

resource "docker_image" "instance_base" {
  name         = var.image
  keep_locally = true
}

resource "docker_container" "instance" {
  name    = var.instance_name
  image   = docker_image.instance_base.image_id
  command = ["sleep", "infinity"] # keeps the container running so Ansible has something to configure

  labels {
    label = "managed-by"
    value = "aiops-remediation-agent"
  }
}

output "instance_name" {
  value = docker_container.instance.name
}

output "instance_id" {
  value = docker_container.instance.id
}
