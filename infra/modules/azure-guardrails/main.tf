# Thalam's Azure guardrails (ADR-0014): the resource group, the Foundry account and project, and
# what fences them. Every number comes from guardrails.json (SPEC-001-R18). The model deployment is
# NOT here: `make foundry-up` / `foundry-down` own it, and the brake deletes it, so Terraform never
# has a deployment to drift from.

locals {
  n    = jsondecode(file("${path.module}/guardrails.json"))
  tags = local.n.tags
}

resource "azurerm_resource_group" "thalam" {
  name     = local.n.resource_group
  location = local.n.region
  tags     = local.tags
}

resource "azurerm_cognitive_account" "foundry" {
  name                       = var.foundry_name
  location                   = azurerm_resource_group.thalam.location
  resource_group_name        = azurerm_resource_group.thalam.name
  kind                       = local.n.policy.allowed_account_kinds[0]
  sku_name                   = "S0"
  custom_subdomain_name      = var.foundry_name
  project_management_enabled = true
  # Phase 0 calls the model with a key in .env (ADR-0012); Phase 2 decides keyless Entra ID.
  local_auth_enabled = true
  tags               = local.tags

  identity {
    type = "SystemAssigned"
  }

  # The fence goes up before anything it fences.
  depends_on = [azurerm_resource_group_policy_assignment.guardrails]
}

resource "azurerm_cognitive_account_project" "thalam" {
  name                 = "thalam"
  display_name         = "Thalam"
  description          = "Thalam's Foundry project (ADR-0012)."
  cognitive_account_id = azurerm_cognitive_account.foundry.id
  location             = azurerm_resource_group.thalam.location
  tags                 = local.tags

  identity {
    type = "SystemAssigned"
  }
}
