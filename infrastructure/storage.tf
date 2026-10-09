resource "aws_s3_bucket" "research_data" {
  bucket_prefix = "${local.name_prefix}-data-"
  force_destroy = true

  tags = {
    Name = "${local.name_prefix}-research-data"
  }
}

resource "aws_s3_bucket_versioning" "research_data" {
  bucket = aws_s3_bucket.research_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "research_data" {
  bucket = aws_s3_bucket.research_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "research_data" {
  bucket = aws_s3_bucket.research_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}