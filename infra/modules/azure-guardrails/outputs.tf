# Names only: no ID, address or key is printed (CLAUDE.md rule 6).

output "resource_group" {
  value = azurerm_resource_group.thalam.name
}

output "action_group" {
  value = azurerm_monitor_action_group.brake.name
}

output "brake_runbook" {
  value = azurerm_automation_runbook.brake.name
}
