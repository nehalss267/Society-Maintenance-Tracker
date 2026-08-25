terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "repositories" {
  description = "ECR repository names to create"
  type        = list(string)
}

resource "aws_ecr_repository" "repos" {
  for_each = toset(var.repositories)

  name         = each.value
  force_delete = true # demo infrastructure

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = each.value }
}

output "repository_urls" {
  value = { for name, repo in aws_ecr_repository.repos : name => repo.repository_url }
}
