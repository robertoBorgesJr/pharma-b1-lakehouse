variable "azure_subscription_id" {
  type        = string
  description = "Azure subscription ID where the Databricks workspace is provisioned"
}

variable "databricks_rg_name" {
  type        = string
  description = "Resource group of the Databricks workspace"
}

variable "databricks_workspace_name" {
  type        = string
  description = "Name of the Databricks workspace"
}
