variable "environment" {
  type        = string
  description = "Environment: 'dev' or 'prod'"
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be 'dev' or 'prod'."
  }
}
