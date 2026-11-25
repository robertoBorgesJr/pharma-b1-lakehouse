# Access Connector must exist in advance (created centrally or reused from workspace governance).
# Databricks serverless compute requires a managed identity access connector —
# service principal storage credentials do not work with serverless.
data "azurerm_databricks_access_connector" "uc_connector" {
  name                = "ext-access-connector-uc"
  resource_group_name = "rg-datamesh-governance-prod"
}

# Storage Account per environment — ADLS Gen2 (HNS enabled).
# Name pattern: st<name><env>, max 24 chars, lowercase alphanumeric only.
resource "azurerm_storage_account" "pharma_b1" {
  name                     = "stpharmab1${var.environment}"
  resource_group_name      = "rg-sap-b1-lab"
  location                 = "eastus2"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  is_hns_enabled           = true
}

# Single ADLS Gen2 container. Dev and prod use separate storage accounts,
# so both can share the same container name without collision.
resource "azurerm_storage_data_lake_gen2_filesystem" "pharma_b1" {
  name               = "pharma-lab-data"
  storage_account_id = azurerm_storage_account.pharma_b1.id
}

# Grant the Access Connector managed identity write access to the storage account.
resource "azurerm_role_assignment" "pharma_b1_contributor" {
  scope                = azurerm_storage_account.pharma_b1.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_databricks_access_connector.uc_connector.identity[0].principal_id
}

# Azure RBAC assignments take 30-90 s to propagate. Without this wait,
# Databricks validates the external location before the role is active → 403.
resource "time_sleep" "wait_role_propagation" {
  depends_on      = [azurerm_role_assignment.pharma_b1_contributor]
  create_duration = "90s"
}

locals {
  container_url = "abfss://${azurerm_storage_data_lake_gen2_filesystem.pharma_b1.name}@${azurerm_storage_account.pharma_b1.name}.dfs.core.windows.net"

  # Prod omits the env suffix to follow the naming convention of existing workspaces.
  external_loc_name = var.environment == "prod" ? "pharma_b1_storage_location" : "pharma_b1_${var.environment}_storage_location"
}

# Storage credential using the Access Connector managed identity.
resource "databricks_storage_credential" "pharma_b1" {
  name    = "pharma_b1_cred_${var.environment}"
  comment = "Pharma lakehouse credential via access connector — serverless compatible"

  azure_managed_identity {
    access_connector_id = data.azurerm_databricks_access_connector.uc_connector.id
  }

  force_destroy = true
  depends_on    = [time_sleep.wait_role_propagation]
}

# External Location covers the whole container; catalogs declare storage_root
# with sub-paths inside this location.
resource "databricks_external_location" "pharma_b1" {
  name            = local.external_loc_name
  url             = "${local.container_url}/"
  credential_name = databricks_storage_credential.pharma_b1.name
  force_destroy   = true

  depends_on = [databricks_storage_credential.pharma_b1]
}

# --- Catalog -----------------------------------------------------------------

resource "databricks_catalog" "pharma_lakehouse" {
  name          = "pharma_lakehouse_${var.environment}"
  storage_root  = "${local.container_url}/pharma_lakehouse/"
  comment       = "Pharma B1 lakehouse — ${var.environment} environment"
  force_destroy = true

  depends_on = [databricks_external_location.pharma_b1]
}

# --- Schemas: SAP Business One -----------------------------------------------

resource "databricks_schema" "bronze_sap_b1" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  name         = "bronze_sap_b1"
  comment      = "Raw SAP B1 data — append-only, original B1 column names, _ingested_at/_batch_id/_source"
}

resource "databricks_schema" "silver_sap_b1" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  name         = "silver_sap_b1"
  comment      = "Conformed SAP B1: typed, deduplicated, English business names, CDF enabled"
}

resource "databricks_schema" "gold_sap_b1" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  name         = "gold_sap_b1"
  comment      = "SAP B1 dimensional model: facts (grain: invoice line) + SCD2 dimensions"
}

# --- Schemas: Salesforce (future phase) --------------------------------------

resource "databricks_schema" "bronze_salesforce" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  name         = "bronze_salesforce"
  comment      = "Raw Salesforce data (Account, Opportunity, Product2) — future phase"
}

resource "databricks_schema" "silver_salesforce" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  name         = "silver_salesforce"
  comment      = "Conformed Salesforce: typed, deduplicated, CDF enabled — future phase"
}

resource "databricks_schema" "gold_salesforce" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  name         = "gold_salesforce"
  comment      = "Salesforce dimensional model — future phase"
}

# --- Schema: Control ---------------------------------------------------------

resource "databricks_schema" "control" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  name         = "control"
  comment      = "Watermarks, run audit, and pipeline control — shared across all sources"
}

# --- Volume: Structured Streaming checkpoints --------------------------------
# Silver uses Structured Streaming (trigger availableNow); checkpoints live here,
# one sub-directory per pipeline (e.g. /checkpoints/silver_ocrd).
resource "databricks_volume" "checkpoints" {
  catalog_name = databricks_catalog.pharma_lakehouse.name
  schema_name  = databricks_schema.control.name
  name         = "checkpoints"
  volume_type  = "MANAGED"
  comment      = "Structured Streaming checkpoints, one sub-directory per pipeline"
}

# --- Grants ------------------------------------------------------------------

resource "databricks_grants" "catalog_pharma_lakehouse" {
  catalog = databricks_catalog.pharma_lakehouse.name
  grant {
    principal  = "account users"
    privileges = ["USE CATALOG"]
  }
}

resource "databricks_grants" "schema_bronze_sap_b1" {
  schema = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.bronze_sap_b1.name}"
  grant {
    principal  = "account users"
    privileges = ["USE SCHEMA", "CREATE TABLE", "MODIFY", "SELECT"]
  }
}

resource "databricks_grants" "schema_silver_sap_b1" {
  schema = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.silver_sap_b1.name}"
  grant {
    principal  = "account users"
    privileges = ["USE SCHEMA", "CREATE TABLE", "MODIFY", "SELECT"]
  }
}

resource "databricks_grants" "schema_gold_sap_b1" {
  schema = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.gold_sap_b1.name}"
  grant {
    principal  = "account users"
    privileges = ["USE SCHEMA", "CREATE TABLE", "MODIFY", "SELECT"]
  }
}

resource "databricks_grants" "schema_bronze_salesforce" {
  schema = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.bronze_salesforce.name}"
  grant {
    principal  = "account users"
    privileges = ["USE SCHEMA", "CREATE TABLE", "MODIFY", "SELECT"]
  }
}

resource "databricks_grants" "schema_silver_salesforce" {
  schema = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.silver_salesforce.name}"
  grant {
    principal  = "account users"
    privileges = ["USE SCHEMA", "CREATE TABLE", "MODIFY", "SELECT"]
  }
}

resource "databricks_grants" "schema_gold_salesforce" {
  schema = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.gold_salesforce.name}"
  grant {
    principal  = "account users"
    privileges = ["USE SCHEMA", "CREATE TABLE", "MODIFY", "SELECT"]
  }
}

resource "databricks_grants" "schema_control" {
  schema = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.control.name}"
  grant {
    principal  = "account users"
    privileges = ["USE SCHEMA", "CREATE TABLE", "MODIFY", "SELECT"]
  }
}

resource "databricks_grants" "volume_checkpoints" {
  volume = "${databricks_catalog.pharma_lakehouse.name}.${databricks_schema.control.name}.${databricks_volume.checkpoints.name}"
  grant {
    principal  = "account users"
    privileges = ["READ VOLUME", "WRITE VOLUME"]
  }
}
