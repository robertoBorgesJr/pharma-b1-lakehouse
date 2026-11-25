module "pharma_b1_dev" {
  source                = "../../modules/pharma_b1_infra"
  environment           = "dev"
}

module "pharma_b1_prod" {
  source                = "../../modules/pharma_b1_infra"
  environment           = "prod"
}

output "dev_catalog_name" {
  value = module.pharma_b1_dev.catalog_name
}

output "prod_catalog_name" {
  value = module.pharma_b1_prod.catalog_name
}

output "dev_checkpoints_volume_path" {
  value = module.pharma_b1_dev.checkpoints_volume_path
}

output "prod_checkpoints_volume_path" {
  value = module.pharma_b1_prod.checkpoints_volume_path
}
