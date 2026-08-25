module "network" {
  source = "../../modules/network"

  project = var.project
}

module "storage" {
  source = "../../modules/storage"

  bucket_name = "${var.project}-assets"
}

module "registry" {
  source = "../../modules/registry"

  repositories = ["${var.project}/api", "${var.project}/web"]
}

# Real EKS costs ~$73/month (control plane) + nodes - created only when
# explicitly enabled. The module code is validated by `terraform validate`.
module "eks" {
  source = "../../modules/eks"
  count  = var.enable_eks ? 1 : 0

  project            = var.project
  subnet_ids         = module.network.public_subnet_ids
  kubernetes_version = var.kubernetes_version
  node_instance_type = var.node_instance_type
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "asset_bucket" {
  value = module.storage.bucket_id
}

output "ecr_urls" {
  value = module.registry.repository_urls
}

output "eks_cluster" {
  value = var.enable_eks ? module.eks[0].cluster_name : null
}
