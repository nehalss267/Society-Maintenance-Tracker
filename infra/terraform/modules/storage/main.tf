terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "bucket_name" {
  description = "Globally unique S3 bucket name for frontend assets / backups"
  type        = string
}

resource "aws_s3_bucket" "assets" {
  bucket        = var.bucket_name
  force_destroy = true # demo infrastructure; real envs should keep false
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id

  versioning_configuration {
    status = "Enabled"
  }
}

output "bucket_id" {
  value = aws_s3_bucket.assets.id
}
