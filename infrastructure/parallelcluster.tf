module "parallelcluster_api" {
  source  = "aws-tf/parallelcluster/aws//modules/pcluster_api"
  version = "1.2.0"

  region         = var.aws_region
  api_stack_name = "${local.name_prefix}-pcluster-api"
  api_version    = var.parallelcluster_api_version

  parameters = {
    EnableIamAdminAccess = "true"
  }
}

locals {
  parallelcluster_config = {
    Region = var.aws_region

    Image = {
      Os = "ubuntu2404"
    }

    HeadNode = {
      InstanceType = "t3.small"

      Ssh = {
        KeyName = aws_key_pair.parallelcluster.key_name
      }

      Networking = {
        SubnetId = aws_subnet.public.id

        AdditionalSecurityGroups = [
          aws_security_group.parallelcluster_head.id
        ]
      }

      Iam = {
        S3Access = [
          {
            BucketName        = aws_s3_bucket.research_data.id
            EnableWriteAccess = true
          }
        ]
      }
    }

    Scheduling = {
      Scheduler = "slurm"

      SlurmQueues = [
        {
          Name         = "spot"
          CapacityType = "SPOT"

          Networking = {
            SubnetIds      = [aws_subnet.public.id]
            AssignPublicIp = true
          }

          Iam = {
            S3Access = [
              {
                BucketName        = aws_s3_bucket.research_data.id
                EnableWriteAccess = true
              }
            ]
          }

          ComputeResources = [
            {
              Name         = "compute"
              InstanceType = "t3.small"
              MinCount     = 0
              MaxCount     = 2
            }
          ]
        }
      ]
    }
  }
}

resource "aws_key_pair" "parallelcluster" {
  key_name   = "${local.name_prefix}-pcluster"
  public_key = file("~/.ssh/id_ed25519.pub")
}

resource "aws_security_group" "parallelcluster_head" {
  name        = "${local.name_prefix}-pcluster-head"
  description = "Additional security group for ParallelCluster head node access"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-pcluster-head"
  }
}

resource "aws_vpc_security_group_ingress_rule" "parallelcluster_head_ssh" {
  security_group_id = aws_security_group.parallelcluster_head.id

  description = "SSH access from administrator IP"
  cidr_ipv4   = var.admin_cidr
  ip_protocol = "tcp"
  from_port   = 22
  to_port     = 22
}

resource "aws_vpc_security_group_egress_rule" "parallelcluster_head_all" {
  security_group_id = aws_security_group.parallelcluster_head.id

  description = "Allow outbound traffic"
  cidr_ipv4   = "0.0.0.0/0"
  ip_protocol = "-1"
}

resource "aws-parallelcluster_cluster" "research" {
  cluster_name = "${local.name_prefix}-cluster"
  region       = var.aws_region

  rollback_on_failure      = true
  validation_failure_level = "WARNING"

  cluster_configuration = yamlencode(local.parallelcluster_config)
}
