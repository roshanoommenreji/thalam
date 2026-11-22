# The brake (ADR-0014, SPEC-001-R16): a runbook that deletes every model deployment on the Foundry
# account. The action group starts it at a budget's brake line; a schedule starts it every night.

resource "azurerm_automation_account" "brake" {
  name                = "thalam-brake"
  location            = azurerm_resource_group.thalam.location
  resource_group_name = azurerm_resource_group.thalam.name
  sku_name            = "Basic" # the first 500 job-minutes a month are free
  tags                = local.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_automation_runtime_environment" "python" {
  name                  = "thalam-python"
  automation_account_id = azurerm_automation_account.brake.id
  location              = azurerm_resource_group.thalam.location
  runtime_language      = "Python"
  runtime_version       = "3.10"
  description           = "Standard library only; the brake needs no packages."
  tags                  = local.tags
}

resource "azurerm_automation_runbook" "brake" {
  name                     = "thalam-brake"
  location                 = azurerm_resource_group.thalam.location
  resource_group_name      = azurerm_resource_group.thalam.name
  automation_account_name  = azurerm_automation_account.brake.name
  runbook_type             = "Python"
  runtime_environment_name = azurerm_automation_runtime_environment.python.name
  log_progress             = true
  log_verbose              = false
  description              = "Deletes every model deployment on Thalam's Foundry account (ADR-0014)."
  tags                     = local.tags

  # The account's ID goes into the uploaded copy only; the file in git keeps the placeholder.
  content = replace(
    file("${path.module}/brake/brake_runbook.py"),
    "__ACCOUNT_ID__",
    azurerm_cognitive_account.foundry.id,
  )
}

resource "azurerm_automation_webhook" "brake" {
  name                    = "thalam-brake-budget"
  resource_group_name     = azurerm_resource_group.thalam.name
  automation_account_name = azurerm_automation_account.brake.name
  runbook_name            = azurerm_automation_runbook.brake.name
  enabled                 = true
  # Azure requires an expiry. It goes in Lab 00's credentials table with a rotate-by date.
  expiry_time = timeadd(timestamp(), "${local.n.brake.webhook_valid_days * 24}h")

  lifecycle {
    ignore_changes = [expiry_time]
  }
}

resource "azurerm_automation_schedule" "nightly" {
  name                    = "thalam-park-nightly"
  resource_group_name     = azurerm_resource_group.thalam.name
  automation_account_name = azurerm_automation_account.brake.name
  frequency               = "Day"
  interval                = 1
  timezone                = local.n.brake.timezone
  description             = "Parks the deployment every night, and runs the brake's whole path daily."
  # The next night in India: the IST date of now + 24 h, at the configured time (+05:30 is IST).
  start_time = "${formatdate("YYYY-MM-DD", timeadd(timestamp(), "29h30m"))}T${local.n.brake.nightly_at}:00+05:30"

  lifecycle {
    ignore_changes = [start_time]
  }
}

resource "azurerm_automation_job_schedule" "nightly" {
  resource_group_name     = azurerm_resource_group.thalam.name
  automation_account_name = azurerm_automation_account.brake.name
  schedule_name           = azurerm_automation_schedule.nightly.name
  runbook_name            = azurerm_automation_runbook.brake.name
}

# Custom roles can be assignable at a resource group, not at a single resource: the role is
# defined on Thalam's group and assigned on the Foundry account only.
resource "azurerm_role_definition" "brake" {
  name        = "Thalam deployment brake"
  scope       = azurerm_resource_group.thalam.id
  description = "Read the Foundry account, and read and delete its model deployments (ADR-0014)."

  permissions {
    actions = [
      "Microsoft.CognitiveServices/accounts/read",
      "Microsoft.CognitiveServices/accounts/deployments/read",
      "Microsoft.CognitiveServices/accounts/deployments/delete",
    ]
  }

  assignable_scopes = [azurerm_resource_group.thalam.id]
}

resource "azurerm_role_assignment" "brake" {
  scope              = azurerm_cognitive_account.foundry.id
  role_definition_id = azurerm_role_definition.brake.role_definition_resource_id
  principal_id       = azurerm_automation_account.brake.identity[0].principal_id
  principal_type     = "ServicePrincipal"
}

resource "azurerm_monitor_action_group" "brake" {
  name                = "thalam-brake"
  resource_group_name = azurerm_resource_group.thalam.name
  short_name          = "thalambrake"
  tags                = local.tags

  email_receiver {
    name                    = "owner"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }

  automation_runbook_receiver {
    name                    = "brake"
    automation_account_id   = azurerm_automation_account.brake.id
    runbook_name            = azurerm_automation_runbook.brake.name
    webhook_resource_id     = azurerm_automation_webhook.brake.id
    service_uri             = azurerm_automation_webhook.brake.uri
    is_global_runbook       = false
    use_common_alert_schema = true
  }
}
