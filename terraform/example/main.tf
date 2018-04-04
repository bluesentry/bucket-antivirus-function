terraform {
  required_version = ">= v0.11.1"
}

provider "aws" {}

data "aws_iam_policy_document" "lambda_s3_antivirus" {
  statement {

    actions = [
      "sts:AssumeRole",
    ]

    principals {
      type = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "lambda_s3_antivirus_role_permissions" {
  statement {

    actions = [
      "s3:*"
    ]

    resources = [
      "arn:aws:s3:::*",
    ]
  }

  statement {

    actions = [
     "logs:CreateLogGroup",
     "logs:CreateLogStream",
     "logs:PutLogEvents",
    ]

    resources = [
      "arn:aws:logs:*"
    ]
  }
}

resource "aws_iam_role_policy" "lambda_antivirus" {
    name = "lambda_antivirus_${var.environment}"
    role = "${aws_iam_role.lambda_antivirus.id}"
    policy = "${data.aws_iam_policy_document.lambda_s3_antivirus_role_permissions.json}"
}

resource "aws_iam_role" "lambda_antivirus" {
    name = "lambda_antivirus_${var.environment}"
    assume_role_policy = "${data.aws_iam_policy_document.lambda_s3_antivirus.json}"
}

resource "aws_lambda_function" "s3_antivirus_scan" {
    filename = "${path.module}/../../build/lambda_antivirus.zip"
    function_name = "s3_antivirus_scan_${var.environment}"
    role = "${aws_iam_role.lambda_antivirus.arn}"
    handler = "scan.lambda_handler"
    runtime = "python2.7"
    environment {
      variables = {
        AV_DEFINITION_S3_BUCKET = "${aws_s3_bucket.s3_antivirus_definitions.id}",
        AV_STATUS_SNS_ARN = "${aws_sns_topic.s3_antivirus_updates.arn}"
      }
    }
    timeout = 300
    memory_size = 1024
}

resource "aws_lambda_permission" "allow_trigger_antivirus_from_s3" {
    statement_id = "AllowExecutionFromS3Bucket"
    action = "lambda:InvokeFunction"
    function_name = "${aws_lambda_function.s3_antivirus_scan.arn}"
    principal = "s3.amazonaws.com"
    source_arn = "${aws_s3_bucket.s3_antivirus_testing.arn}"
}

resource "aws_lambda_function" "s3_antivirus_update" {
    filename = "${path.module}/files/lambda_antivirus.zip"
    function_name = "s3_antivirus_update_${var.environment}"
    role = "${aws_iam_role.lambda_antivirus.arn}"
    handler = "update.lambda_handler"
    runtime = "python2.7"
    environment {
      variables = {
        AV_DEFINITION_S3_BUCKET = "${aws_s3_bucket.s3_antivirus_definitions.id}"
      }
    }

    # Requirements specified in https://github.com/upsidetravel/bucket-antivirus-function
    timeout = 300
    memory_size = 512
}

# Cloudwatch in order to update AV definitions

resource "aws_cloudwatch_event_rule" "lambda_s3_antivirus_update_interval" {
    name = "update-av-every-3h-${var.environment}"
    description = "Updates antivirus clamav every 3 hours"
    schedule_expression = "rate(3 hours)"

}

resource "aws_cloudwatch_event_target" "create_lambda_s3_antivitus_update" {
    rule = "${aws_cloudwatch_event_rule.lambda_s3_antivirus_update_interval.name}"
    arn = "${aws_lambda_function.s3_antivirus_update.arn}"
}


resource "aws_lambda_permission" "allow_cloudwatch_to_call_lambda_s3_antivirus_update" {
    statement_id = "AllowExecutionFromCloudWatch"
    action = "lambda:InvokeFunction"
    function_name = "${aws_lambda_function.s3_antivirus_update.function_name}"
    principal = "events.amazonaws.com"
    source_arn = "${aws_cloudwatch_event_rule.lambda_s3_antivirus_update_interval.arn}"
}

resource "aws_s3_bucket" "s3_antivirus_definitions" {
  bucket = "s3_antivirus_definitions_${var.environment}"
  acl    = "private"
}

resource "aws_s3_bucket" "s3_antivirus_testing" {
  bucket = "s3_antivirus_testing_${var.environment}"
  acl    = "private"
}

resource "aws_s3_bucket_notification" "antivirus_scan" {
  bucket = "${aws_s3_bucket.s3_antivirus_testing.id}"

  lambda_function {
    lambda_function_arn = "${aws_lambda_function.s3_antivirus_scan.arn}"
    events = ["s3:ObjectCreated:*"]
  }
}


resource "aws_sns_topic" "s3_antivirus_updates" {
  name = "s3-antivirus-updates-${var.environment}"
}

resource "aws_sqs_queue" "s3_antivirus_queue" {
  name = "s3-antivirus-queue-${var.environment}"
}

resource "aws_sns_topic_subscription" "s3_antivirus_updates_sqs_target" {
  topic_arn = "${aws_sns_topic.s3_antivirus_updates.arn}"
  protocol  = "sqs"
  endpoint  = "${aws_sqs_queue.s3_antivirus_queue.arn}"
}
