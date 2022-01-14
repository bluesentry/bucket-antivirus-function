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
    statement {
      sid = "AllowSelfLogging"
      effect = "Allow"
      principals {
        type        = "Service"
        identifiers = ["logging.s3.amazonaws.com"]
      }
      actions = [
        "s3:PutObject",
        "s3:PutObjectAcl"
      ]
      resources = ["arn:aws:s3:::nc-${var.env_name}-s3-clamscan-builds/self-logs/*"]
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
  logging {
    target_bucket = "nc-${var.env_name}-s3-clamscan-builds"
    target_prefix = "self-logs/"
  }
  versioning {
    enabled = true
  }
}

# Block all public access to our S3 bucket
resource "aws_s3_bucket_public_access_block" "s3_clamscan_builds" {
  bucket = aws_s3_bucket.builds.id
  block_public_acls = true
  block_public_policy = true
  restrict_public_buckets = true
  ignore_public_acls = true
}

resource "aws_s3_bucket_object" "build" {
    bucket = aws_s3_bucket.builds.id
    key    = local.lambda_package_key
    source = "/tmp/lambda.zip"
}
