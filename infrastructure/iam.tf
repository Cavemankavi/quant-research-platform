data "aws_iam_policy_document" "compute_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_service_linked_role" "ec2_spot" {
  aws_service_name = "spot.amazonaws.com"
}

resource "aws_iam_role" "compute" {
  name               = "${local.name_prefix}-compute"
  assume_role_policy = data.aws_iam_policy_document.compute_assume_role.json
}

data "aws_iam_policy_document" "research_data_access" {
  statement {
    sid = "ListResearchBucket"

    actions = [
      "s3:ListBucket"
    ]

    resources = [
      aws_s3_bucket.research_data.arn
    ]
  }

  statement {
    sid = "ResearchObjectAccess"

    actions = [
      "s3:GetObject",
      "s3:PutObject"
    ]

    resources = [
      "${aws_s3_bucket.research_data.arn}/*"
    ]
  }
}

resource "aws_iam_policy" "research_data_access" {
  name   = "${local.name_prefix}-research-data-access"
  policy = data.aws_iam_policy_document.research_data_access.json
}

resource "aws_iam_role_policy_attachment" "compute_research_data" {
  role       = aws_iam_role.compute.name
  policy_arn = aws_iam_policy.research_data_access.arn
}

resource "aws_iam_instance_profile" "compute" {
  name = "${local.name_prefix}-compute"
  role = aws_iam_role.compute.name
}