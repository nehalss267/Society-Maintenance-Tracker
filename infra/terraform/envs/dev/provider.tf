terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Route AWS API calls to LocalStack for free CI validation
  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      ec2 = "http://localhost:4566"
      s3  = "http://localhost:4566"
      ecr = "http://localhost:4566"
      iam = "http://localhost:4566"
      sts = "http://localhost:4566"
      eks = "http://localhost:4566"
    }
  }

  # LocalStack accepts static dummy credentials
  access_key = var.use_localstack ? "test" : null
  secret_key = var.use_localstack ? "test" : null

  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack

  default_tags {
    tags = {
      Project   = "society-maintenance-tracker"
      ManagedBy = "terraform"
    }
  }
}
