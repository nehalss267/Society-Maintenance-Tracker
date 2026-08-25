variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project prefix for resource naming"
  type        = string
  default     = "smt"
}

variable "use_localstack" {
  description = "Point providers at LocalStack instead of real AWS (CI validation)"
  type        = bool
  default     = false
}

variable "enable_eks" {
  description = "Create the EKS cluster + node group. Requires real AWS (bills ~$73/mo control plane). LocalStack community cannot emulate EKS."
  type        = bool
  default     = false
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version"
  type        = string
  default     = "1.31"
}

variable "node_instance_type" {
  description = "EC2 instance type for the EKS managed node group"
  type        = string
  default     = "t3.small"
}
