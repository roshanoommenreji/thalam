# The two budgets (ADR-0013), in the billing currency (INR). Each alert e-mails; the alert at a
# budget's brake line also goes to the action group, which starts the brake (ADR-0014, SPEC-001-R16).

resource "azurerm_consumption_budget_resource_group" "budget" {
  for_each = local.n.budgets

  name              = each.key
  resource_group_id = azurerm_resource_group.thalam.id
  amount            = each.value.amount
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00Z", timestamp())
  }

  # thalam-model counts the Foundry account only; thalam-total counts the whole group.
  dynamic "filter" {
    for_each = each.value.scope == "foundry-account" ? ["foundry"] : []
    content {
      dimension {
        name   = "ResourceId"
        values = [lower(azurerm_cognitive_account.foundry.id)]
      }
    }
  }

  dynamic "notification" {
    for_each = each.value.alerts
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = [var.alert_email]
      contact_groups = notification.value == each.value.brake_at ? [azurerm_monitor_action_group.brake.id] : []
    }
  }

  lifecycle {
    ignore_changes = [time_period] # the start date is set once, on the month it was created
  }
}
