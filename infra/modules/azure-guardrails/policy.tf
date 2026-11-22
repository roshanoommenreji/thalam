# One initiative, assigned once on Thalam's resource group (ADR-0014, SPEC-001-R15). The three
# custom rules are in policy/*.json and hold no numbers; their parameters come from guardrails.json.

locals {
  rules = {
    for name in ["accounts", "deployments", "search"] :
    name => jsondecode(file("${path.module}/policy/${name}.json"))
  }
  builtin = "/providers/Microsoft.Authorization/policyDefinitions"
}

resource "azurerm_policy_definition" "rule" {
  for_each = local.rules

  name         = "thalam-${each.key}"
  policy_type  = "Custom"
  mode         = each.value.mode
  display_name = each.value.displayName
  description  = each.value.description
  parameters   = jsonencode(each.value.parameters)
  policy_rule  = jsonencode(each.value.policyRule)
}

resource "azurerm_policy_set_definition" "guardrails" {
  name         = local.n.policy.assignment
  policy_type  = "Custom"
  display_name = "Thalam cost guardrails (ADR-0014)"
  description  = "One region, the approved model at a capped capacity, Foundry accounts only, AI Search on Free, and nothing that runs all month."

  policy_definition_reference {
    reference_id         = "allowed-locations"
    policy_definition_id = "${local.builtin}/e56962a6-4747-49cd-b67b-bf8b01975c4c" # Allowed locations
    parameter_values = jsonencode({
      listOfAllowedLocations = { value = local.n.policy.allowed_locations }
    })
  }

  policy_definition_reference {
    reference_id         = "not-allowed-types"
    policy_definition_id = "${local.builtin}/6c112d4e-5bc7-47ae-a041-ea2d9dccd749" # Not allowed resource types
    parameter_values = jsonencode({
      listOfResourceTypesNotAllowed = { value = local.n.policy.not_allowed_types }
    })
  }

  policy_definition_reference {
    reference_id         = "deployments"
    policy_definition_id = azurerm_policy_definition.rule["deployments"].id
    parameter_values = jsonencode({
      allowedModels = { value = [local.n.model.name] }
      allowedSkus   = { value = [local.n.model.sku] }
      maxCapacity   = { value = local.n.model.capacity_cap }
    })
  }

  policy_definition_reference {
    reference_id         = "accounts"
    policy_definition_id = azurerm_policy_definition.rule["accounts"].id
    parameter_values = jsonencode({
      allowedKinds = { value = local.n.policy.allowed_account_kinds }
    })
  }

  policy_definition_reference {
    reference_id         = "search"
    policy_definition_id = azurerm_policy_definition.rule["search"].id
    parameter_values = jsonencode({
      allowedSkus = { value = local.n.policy.allowed_search_skus }
    })
  }
}

resource "azurerm_resource_group_policy_assignment" "guardrails" {
  name                 = local.n.policy.assignment
  display_name         = "Thalam cost guardrails (ADR-0014)"
  resource_group_id    = azurerm_resource_group.thalam.id
  policy_definition_id = azurerm_policy_set_definition.guardrails.id

  non_compliance_message {
    content = "Refused by Thalam's cost guardrails (ADR-0014). Changing them needs an ADR, written before the change."
  }
}
