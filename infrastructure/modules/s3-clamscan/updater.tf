#
# Lambda Function: Anti-Virus Definitions
#

#
# IAM
#

data "aws_iam_policy_document" "assume_role_update" {
  statement {
    effect = "Allow"

    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "main_update" {
  # Allow creating and writing CloudWatch logs for Lambda function.
  statement {
    sid = "WriteCloudWatchLogs"

    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/s3-clamscan-updater:*"]
  }

  statement {
    sid = "s3GetAndPutWithTagging"

    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectTagging",
      "s3:PutObject",
      "s3:PutObjectTagging",
      "s3:PutObjectVersionTagging",
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
}

resource "aws_iam_role" "main_update" {
  name                 = "lmbrole-${var.env_name}-s3-clamscan-updater"
  assume_role_policy   = data.aws_iam_policy_document.assume_role_update.json
  tags = {
    "name"      = "lmbrole-${var.env_name}-s3-clamscan-updater"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "no"
  }
}

resource "aws_iam_role_policy" "main_update" {
  name = "policy-nc-${var.env_name}-s3-clamscan-updater"
  role = aws_iam_role.main_update.id

  policy = data.aws_iam_policy_document.main_update.json
}

#
# CloudWatch Scheduled Event
#

resource "aws_cloudwatch_event_rule" "main_update" {
  name                = "cwer-${var.env_name}-s3-clamscan-updater"
  description         = "scheduled trigger for s3-clamscan-updater"
  schedule_expression = "rate(${var.av_update_minutes} minutes)"
  tags = {
    "name"      = "cwer-${var.env_name}-s3-clamscan-updater"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "no"
  }
}

resource "aws_cloudwatch_event_target" "main_update" {
  rule = aws_cloudwatch_event_rule.main_update.name
  arn  = aws_lambda_function.main_update.arn
}

#
# CloudWatch Logs
#

resource "aws_cloudwatch_log_group" "main_update" {
  # This name must match the lambda function name and should not be changed
  name              = "/aws/lambda/lmb-${var.env_name}-s3-clamscan-updater"
  retention_in_days = var.cloudwatch_logs_retention_days

  tags = {
    "name"      = "lmb-${var.env_name}-s3-clamscan-updater"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "yes"
  }
}

resource "aws_cloudwatch_log_subscription_filter" "s3_clamscan_updater_subscription_filter" {
  name            = "datadog_log_subscription_filter"
  log_group_name  = aws_cloudwatch_log_group.main_update.name
  destination_arn = "arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:lmb-${var.env_name}-datadog-forwarder"
  filter_pattern  = ""
}

#
# Lambda Function
#

resource "aws_lambda_function" "main_update" {
  depends_on = [aws_cloudwatch_log_group.main_update]

  description = "Updates clamav definitions stored in s3."

  s3_bucket = aws_s3_bucket.builds.id
  s3_key    = aws_s3_bucket_object.build.id

  function_name = "lmb-${var.env_name}-s3-clamscan-updater"
  role          = aws_iam_role.main_update.arn
  handler       = "update.lambda_handler"
  runtime       = "python3.7"
  memory_size   = var.memory_size
  timeout       = var.timeout_seconds

  environment {
    variables = {
      AV_DEFINITION_S3_BUCKET = aws_s3_bucket.virus_definitions.id
      AV_DEFINITION_S3_PREFIX = var.lambda_package
    }
  }

  tags = {
    "name"      = "lmb-${var.env_name}-s3-clamscan-updater"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "yes"
  }
}

resource "aws_lambda_permission" "main_update" {
  statement_id = "AllowExecutionFromCloudWatch"

  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main_update.function_name

  principal  = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.main_update.arn
}
