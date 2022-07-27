data "aws_iam_policy_document" "s3_malware_scanner_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "s3_malware_scanner_def_inline" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:PutObjectVersionTagging",
      "s3:GetObjectTagging",
      "s3:ListBucket",
      "s3:PutObjectTagging"
    ]
    resources = [
      "arn:aws:s3:::${var.environment}-${var.definitions}/*",
      "arn:aws:s3:::${var.environment}-${var.definitions}"
    ]
  }

  statement {
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey"
    ]
    resources = [aws_kms_key.definitions_bucket_key.arn]
  }

  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "s3_malware_scanner_inline" {
  statement {
    actions = [
      "kms:Decrypt",
      "sns:Publish",
      "s3:ListBucket"
    ]
    resources = [
      var.scan_bucket_arn,
      "arn:aws:s3:::${var.environment}-${var.definitions}/*",
      "arn:aws:s3:::${var.environment}-${var.definitions}",
      var.kms_key_for_scan_bucket,
      aws_sns_topic.scan_results.arn
    ]
  }

  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }

  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObjectVersionTagging",
      "s3:GetObjectTagging",
      "s3:PutObjectTagging",
      "s3:GetObjectVersion"
    ]
    resources = [var.scan_bucket_arn, "${var.scan_bucket_arn}/*"]
  }

  statement {
    actions = [
      "s3:GetObject",
      "s3:GetObjectTagging"
    ]
    resources = ["arn:aws:s3:::${var.environment}-${var.definitions}/*"]
  }


}

resource "aws_iam_role" "s3_malware_scanner_definitions_lambda" {
  name               = "S3MalwareScannerDefinitionsLambda"
  assume_role_policy = data.aws_iam_policy_document.s3_malware_scanner_assume_role.json
  inline_policy {
    name   = "S3MalwareScannerDefinitionsLambdaPolicy"
    policy = data.aws_iam_policy_document.s3_malware_scanner_def_inline.json
  }
}

resource "aws_iam_role" "s3_malware_scanner_lambda" {
  name               = "S3MalwareScannerLambda"
  assume_role_policy = data.aws_iam_policy_document.s3_malware_scanner_assume_role.json
  inline_policy {
    name   = "S3MalwareScannerLambdaPolicy"
    policy = data.aws_iam_policy_document.s3_malware_scanner_inline.json
  }

}
