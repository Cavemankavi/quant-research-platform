terraform {
  backend "s3" {
    bucket       = "kaviyan-tf-state"
    key          = "quant-research-platform/dev/terraform.tfstate"
    region       = "ap-southeast-1"
    encrypt      = true
    use_lockfile = true
  }
}