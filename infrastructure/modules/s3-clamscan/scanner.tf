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
    sid = "sqsReceiveAndDelete"

    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage"
    ]

    resources = [aws_sqs_queue.messages.arn]
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
# Scheduled trigger
#

resource "aws_cloudwatch_event_rule" "main_scan" {
  name                = "cwer-${var.env_name}-s3-clamscan-scanner"
  description         = "scheduled trigger for s3-clamscan-scanner"
  schedule_expression = "rate(${var.av_scan_minutes} minute)"
  tags = {
    "name"      = "cwer-${var.env_name}-s3-clamscan-scanner"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "no"
  }
}

resource "aws_cloudwatch_event_target" "main_scan" {
  rule = aws_cloudwatch_event_rule.main_scan.name
  arn  = aws_lambda_function.main_scan.arn
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
      AV_SCAN_BUCKET_NAME            = data.aws_s3_bucket.main_scan[0].id
      AV_STATUS_SNS_ARN              = var.av_status_sns_arn
      AV_STATUS_SNS_PUBLISH_CLEAN    = var.av_status_sns_publish_clean
      AV_STATUS_SNS_PUBLISH_INFECTED = var.av_status_sns_publish_infected
      AV_DELETE_INFECTED_FILES       = var.av_delete_infected_files
      SQS_QUEUE_URL                  = aws_sqs_queue.messages.url
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
  statement_id = "AllowExecutionFromCloudWatch"

  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main_scan.function_name

  principal  = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.main_scan.arn
}
