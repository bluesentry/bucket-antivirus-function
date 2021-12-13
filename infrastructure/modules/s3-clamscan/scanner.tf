#
# Lambda Function: Anti-Virus Scanning
#

#
# IAM
#

data "aws_iam_policy_document" "assume_role_scan" {
  statement {
    effect = "Allow"

    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "main_scan" {
  # Allow creating and writing CloudWatch logs for Lambda function.
  statement {
    sid = "WriteCloudWatchLogs"

    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/lmb-${var.env_name}-s3-clamscan-scanner:*"]
  }

  statement {
    sid = "s3AntiVirusScan"

    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectTagging",
      "s3:GetObjectVersion",
      "s3:PutObjectTagging",
      "s3:PutObjectVersionTagging",
    ]

    resources = formatlist("%s/*", data.aws_s3_bucket.main_scan.*.arn)
  }

  statement {
    sid = "s3AntiVirusDefinitions"

    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectTagging",
    ]

    resources = ["arn:${data.aws_partition.current.partition}:s3:::${aws_s3_bucket.virus_definitions.id}/${var.lambda_package}/*"]
  }

  statement {
    sid = "s3HeadObject"

    effect = "Allow"

    actions = [
      "s3:ListBucket",
    ]

    resources = [
      "arn:${data.aws_partition.current.partition}:s3:::${aws_s3_bucket.virus_definitions.id}",
      "arn:${data.aws_partition.current.partition}:s3:::${aws_s3_bucket.virus_definitions.id}/*",
    ]
  }

  statement {
    sid = "kmsDecrypt"

    effect = "Allow"

    actions = [
      "kms:Decrypt",
    ]

    resources = formatlist("%s/*", data.aws_s3_bucket.main_scan.*.arn)
  }

  dynamic "statement" {
    for_each = length(compact([var.av_scan_start_sns_arn, var.av_status_sns_arn])) != 0 ? toset([0]) : toset([])

    content {
      sid = "snsPublish"

      actions = [
        "sns:Publish",
      ]

      resources = compact([var.av_scan_start_sns_arn, var.av_status_sns_arn])
    }
  }
}

resource "aws_iam_role" "main_scan" {
  name                 = "lmbrole-${var.env_name}-s3-clamscan-scanner"
  assume_role_policy   = data.aws_iam_policy_document.assume_role_scan.json
  tags = {
    "name"      = "lmbrole-${var.env_name}-s3-clamscan-scanner"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "no"
  }
}

resource "aws_iam_role_policy" "main_scan" {
  name = "policy-nc-${var.env_name}-s3-clamscan-scanner"
  role = aws_iam_role.main_scan.id

  policy = data.aws_iam_policy_document.main_scan.json
}

#
# S3 Event
#

data "aws_s3_bucket" "main_scan" {
  count  = length(var.av_scan_buckets)
  bucket = var.av_scan_buckets[count.index]
}

resource "aws_s3_bucket_notification" "main_scan" {
  count  = length(var.av_scan_buckets)
  bucket = element(data.aws_s3_bucket.main_scan.*.id, count.index)

  lambda_function {
    id                  = element(data.aws_s3_bucket.main_scan.*.id, count.index)
    lambda_function_arn = aws_lambda_function.main_scan.arn
    events              = ["s3:ObjectCreated:*"]
  }
}

#
# CloudWatch Logs
#

resource "aws_cloudwatch_log_group" "main_scan" {
  # This name must match the lambda function name and should not be changed
  name              = "/aws/lambda/lmb-${var.env_name}-s3-clamscan-scanner"
  retention_in_days = var.cloudwatch_logs_retention_days

  tags = {
    "name"      = "lmb-${var.env_name}-s3-clamscan-scanner"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "yes"
  }
}

#
# Lambda Function
#

resource "aws_lambda_function" "main_scan" {
  depends_on = [aws_cloudwatch_log_group.main_scan]

  description = "Scans s3 objects with clamav for viruses."

  s3_bucket = aws_s3_bucket.builds.id
  s3_key    = aws_s3_bucket_object.build.id

  function_name = "lmb-${var.env_name}-s3-clamscan-scanner"
  role          = aws_iam_role.main_scan.arn
  handler       = "scan.lambda_handler"
  runtime       = "python3.7"
  memory_size   = var.memory_size
  timeout       = var.timeout_seconds

  environment {
    variables = {
      AV_DEFINITION_S3_BUCKET        = aws_s3_bucket.virus_definitions.id
      AV_DEFINITION_S3_PREFIX        = var.lambda_package
      AV_SCAN_START_SNS_ARN          = var.av_scan_start_sns_arn
      AV_STATUS_SNS_ARN              = var.av_status_sns_arn
      AV_STATUS_SNS_PUBLISH_CLEAN    = var.av_status_sns_publish_clean
      AV_STATUS_SNS_PUBLISH_INFECTED = var.av_status_sns_publish_infected
      AV_DELETE_INFECTED_FILES       = var.av_delete_infected_files
    }
  }

  tags = {
    "name"      = "lmb-${var.env_name}-s3-clamscan-scanner"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "yes"
  }
}

resource "aws_lambda_permission" "main_scan" {
  count = length(var.av_scan_buckets)

  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main_scan.function_name

  principal = "s3.amazonaws.com"

  source_account = var.aws_account_id
  source_arn     = element(data.aws_s3_bucket.main_scan.*.arn, count.index)

  statement_id = replace("lmb-${var.env_name}-s3-clamscan-scanner-${element(data.aws_s3_bucket.main_scan.*.id, count.index)}", ".", "-")
}
