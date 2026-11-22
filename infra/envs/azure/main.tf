# Thalam's one Azure environment in Phases 0–6 (ADR-0012, ADR-0014). State stays on the laptop and is
# gitignored. The subscription comes from `az account show` (ARM_SUBSCRIPTION_ID, set by the
# Makefile); the Foundry name and the alert e-mail come from .env (TF_VAR_*). Run it through
# `make guardrails-plan` and `make guardrails-apply`.

terraform {
  required_version = ">= 1.11"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.14"
    }
  }
}

provider "azurerm" {
  # azurerm 5 registers no resource providers by itself; Lab 00 registers the few Thalam needs.
  resource_provider_registrations = "none"

  features {
    cognitive_account {
      # A deleted account is soft-deleted and keeps its name; purge it so a rebuild can reuse it.
      purge_soft_delete_on_destroy = true
    }
  }
}

variable "foundry_name" {
  type      = string
  sensitive = true
}

variable "alert_email" {
  type      = string
  sensitive = true
}

module "guardrails" {
  source       = "../../modules/azure-guardrails"
  foundry_name = var.foundry_name
  alert_email  = var.alert_email
}

output "guardrails" {
  value = module.guardrails
}
