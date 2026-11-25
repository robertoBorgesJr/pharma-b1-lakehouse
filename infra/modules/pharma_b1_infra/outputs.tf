output "catalog_name" {
  description = "Unity Catalog name for the pharma lakehouse (pharma_lakehouse_<env>)"
  value       = databricks_catalog.pharma_lakehouse.name
}

output "external_location_url" {
  description = "URL of the External Location covering the ADLS Gen2 container"
  value       = databricks_external_location.pharma_b1.url
}

output "checkpoints_volume_path" {
  description = "Unity Catalog path for Structured Streaming checkpoints (silver layer)"
  value       = "/Volumes/${databricks_catalog.pharma_lakehouse.name}/control/checkpoints"
}

output "storage_account_name" {
  description = "Azure Storage Account name (useful for diagnosing access issues)"
  value       = azurerm_storage_account.pharma_b1.name
}
