variable "aws_region" {
  description = "AWS region for the research platform"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "quant-research-platform"
}

variable "parallelcluster_api_version" {
  description = "AWS ParallelCluster API version"
  type        = string
  default     = "3.15.1"
}

variable "admin_cidr" {
  description = "CIDR allowed to SSH to the ParallelCluster head node"
  type        = string
}