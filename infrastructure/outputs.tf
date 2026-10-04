output "research_data_bucket" {
  description = "S3 bucket containing research datasets and results"
  value       = aws_s3_bucket.research_data.id
}

output "parallelcluster_api_outputs" {
  description = "Outputs from the ParallelCluster API stack"
  value       = module.parallelcluster_api.stack_outputs
}

output "parallelcluster_name" {
  description = "Name of the research Slurm cluster"
  value       = aws-parallelcluster_cluster.research.cluster_name
}

output "parallelcluster_status" {
  description = "Status of the research Slurm cluster"
  value       = aws-parallelcluster_cluster.research.cluster_status
}