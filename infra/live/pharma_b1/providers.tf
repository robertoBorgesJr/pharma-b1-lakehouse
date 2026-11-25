terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.40"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

provider "azurerm" {
  features {}
  storage_use_azuread = true
}

# Authenticates to the Databricks workspace via ARM resource ID.
# Local dev: relies on az CLI login (az login).
# CI/CD: replace inline with service principal vars:
#   client_id     = var.sp_client_id
#   client_secret = var.sp_client_secret
#   tenant_id     = var.tenant_id
provider "databricks" {
  azure_workspace_resource_id = "/subscriptions/${var.azure_subscription_id}/resourceGroups/${var.databricks_rg_name}/providers/Microsoft.Databricks/workspaces/${var.databricks_workspace_name}"
}
