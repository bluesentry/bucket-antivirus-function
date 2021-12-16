#
# S3 Bucket: Build Artifacts
#

#
# IAM
#

data "aws_iam_policy_document" "builds_bucket_policy" {
    statement {
        sid = "ForceSSLOnlyAccess"
        effect = "Deny"
        principals {
            type        = "*"
            identifiers = ["*"]
        }
        actions = ["*"]
        resources = ["arn:aws:s3:::nc-${var.env_name}-s3-clamscan-builds/*"]
        condition {
            test = "Bool"
            variable = "aws:SecureTransport"
            values = ["false"]
        }
    }
}

#
# S3 Bucket
#

resource "aws_s3_bucket" "builds" {
  bucket = "nc-${var.env_name}-s3-clamscan-builds"

  acl = "private"
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  policy = data.aws_iam_policy_document.builds_bucket_policy.json

  tags = {
    "name"      = "nc-${var.env_name}-s3-clamscan-builds"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "no"
  }

  lifecycle_rule {
      enabled = false # this bucket is used to store code for the lambda functions, objects should never be aged out
  }
}

resource "aws_s3_bucket_object" "build" {
    bucket = aws_s3_bucket.builds.id
    key    = local.lambda_package_key
    source = "/tmp/lambda.zip"
}
