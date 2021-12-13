#
# S3 Bucket: Virus Definitions
#

#
# IAM
#

data "aws_iam_policy_document" "virus_definitions_bucket_policy" {
    statement {
        sid = "ForceSSLOnlyAccess"
        effect = "Deny"
        principals {
            type        = "*"
            identifiers = ["*"]
        }
        actions = ["*"]
        resources = ["arn:aws:s3:::nc-${var.env_name}-s3-clamscan-definitions/*"]
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

resource "aws_s3_bucket" "virus_definitions" {
  bucket = "nc-${var.env_name}-s3-clamscan-definitions"

  acl = "private"
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  policy = data.aws_iam_policy_document.virus_definitions_bucket_policy.json

  tags = {
    "name"      = "nc-${var.env_name}-s3-clamscan-definitions"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "no"
  }

  lifecycle_rule {
      enabled = false # this bucket is used to store definitions for the scanner lambda, objects should never be aged out
  }
}
