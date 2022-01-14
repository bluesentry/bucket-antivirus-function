#
# Lambda Function: SQS Message Publisher
#

#
# IAM
#

data "aws_iam_policy_document" "assume_role_publish" {
  statement {
    effect = "Allow"

    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "main_publish" {
  # Allow creating and writing CloudWatch logs for Lambda function.
  statement {
    sid = "WriteCloudWatchLogs"

    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["arn:${data.aws_partition.current.partition}:logs:${var.aws_region}:${var.aws_account_id}:log-group:/aws/lambda/lmb-${var.env_name}-s3-clamscan-publisher:*"]
  }
  # Allow writing messages to SQS queue
  statement {
    sid = "WriteMessagesToSQS"

    effect = "Allow"

    actions = [
        "sqs:SendMessage"
    ]

    resources = [aws_sqs_queue.messages.arn]
  }
}

resource "aws_iam_role" "main_publish" {
  name                 = "lmbrole-${var.env_name}-s3-clamscan-publisher"
  assume_role_policy   = data.aws_iam_policy_document.assume_role_publish.json
  tags = {
    "name"      = "lmbrole-${var.env_name}-s3-clamscan-publisher"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "no"
  }
}

resource "aws_iam_role_policy" "main_publish" {
  name = "policy-nc-${var.env_name}-s3-clamscan-publisher"
  role = aws_iam_role.main_publish.id

  policy = data.aws_iam_policy_document.main_publish.json
}

#
# CloudWatch Logs
#

resource "aws_cloudwatch_log_group" "main_publish" {
  # This name must match the lambda function name and should not be changed
  name              = "/aws/lambda/lmb-${var.env_name}-s3-clamscan-publisher"
  retention_in_days = var.cloudwatch_logs_retention_days

  tags = {
    "name"      = "lmb-${var.env_name}-s3-clamscan-publisher"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "yes"
  }
}

resource "aws_cloudwatch_log_subscription_filter" "s3_clamscan_publisher_subscription_filter" {
  name            = "datadog_log_subscription_filter"
  log_group_name  = aws_cloudwatch_log_group.main_publish.name
  destination_arn = "arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:lmb-${var.env_name}-datadog-forwarder"
  filter_pattern  = ""
}

#
# Lambda Function
#

resource "aws_lambda_function" "main_publish" {
  depends_on = [aws_cloudwatch_log_group.main_publish]

  description = "Publishes object names to SQS for scanner to consume."

  s3_bucket = aws_s3_bucket.builds.id
  s3_key    = aws_s3_bucket_object.build.id

  function_name = "lmb-${var.env_name}-s3-clamscan-publisher"
  role          = aws_iam_role.main_publish.arn
  handler       = "publish.lambda_handler"
  runtime       = "python3.7"
  memory_size   = var.publisher_memory_size
  timeout       = var.timeout_seconds

  environment {
    variables = {
      SQS_QUEUE_URL = aws_sqs_queue.messages.url
    }
  }

  tags = {
    "name"      = "lmb-${var.env_name}-s3-clamscan-publisher"
    "app"       = "s3-clamscan"
    "env"       = var.env_name
    "team"      = "sre"
    "sensitive" = "yes"
  }
}

# Allows target bucket(s) to invoke this function
data "aws_s3_bucket" "main_scan" {
  count  = length(var.av_scan_buckets)
  bucket = var.av_scan_buckets[count.index]
}

resource "aws_lambda_permission" "main_publish" {
  count = length(var.av_scan_buckets)

  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main_publish.function_name

  principal = "s3.amazonaws.com"

  source_account = var.aws_account_id
  source_arn     = element(data.aws_s3_bucket.main_scan.*.arn, count.index)

  statement_id = replace("lmb-${var.env_name}-s3-clamscan-publisher-${element(data.aws_s3_bucket.main_scan.*.id, count.index)}", ".", "-")
}

# Notification for target bucket(s)
resource "aws_s3_bucket_notification" "main_publish" {
  count  = length(var.av_scan_buckets)
  bucket = element(data.aws_s3_bucket.main_scan.*.id, count.index)

  lambda_function {
    id                  = element(data.aws_s3_bucket.main_scan.*.id, count.index)
    lambda_function_arn = aws_lambda_function.main_publish.arn
    events              = ["s3:ObjectCreated:*"]
  }
}
