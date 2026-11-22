# Both values come from .env through scripts/ops/tf.py (TF_VAR_*), so neither is in git (rule 6).

variable "foundry_name" {
  description = "The Foundry account's name, which is also its subdomain (its address)."
  type        = string
  sensitive   = true # hidden in plan output, like the e-mail

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$", var.foundry_name))
    error_message = "foundry_name must be a resource name (lowercase letters, digits, hyphens), not a URL."
  }
}

variable "alert_email" {
  description = "Where every budget alert and the brake's notice are e-mailed."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be an e-mail address."
  }
}
