terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    aws-parallelcluster = {
      source  = "aws-tf/aws-parallelcluster"
      version = "~> 1.2"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "quant-research-platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

provider "aws-parallelcluster" {
  region         = var.aws_region
  api_stack_name = module.parallelcluster_api.stack_name
  use_user_role  = true
}