resource "aws_s3_bucket" "av_definitions_bucket" {
  bucket = "${var.av_definitions_bucket}"
  acl    = "private"
}

resource "aws_iam_role" "av_definitions_access" {
  name = "av_definitions_access"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

resource "aws_iam_role_policy" "av_definitions_access_policy" {
  policy = <<EOF
{
   "Version":"2012-10-17",
   "Statement":[
      {
         "Effect":"Allow",
         "Action":[
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
         ],
         "Resource":"*"
      },
      {
         "Action":[
            "s3:GetObject",
            "s3:GetObjectTagging",
            "s3:PutObject",
            "s3:PutObjectTagging",
            "s3:PutObjectVersionTagging"
         ],
         "Effect":"Allow",
         "Resource":"arn:aws:s3:::${aws_s3_bucket.av_definitions_bucket.bucket}/*"
      }
   ]
}
EOF
  role = "${aws_iam_role.av_definitions_access.id}"
}

resource "aws_lambda_function" "update_av_definitions" {
  filename         = "build/lambda.zip"
  function_name    = "update_av_definitions"
  role             = "${aws_iam_role.av_definitions_access.arn}"
  source_code_hash = "${base64sha256(file("build/lambda.zip"))}"
  runtime          = "python2.7"
  handler          = "update.lambda_handler"
  timeout          = 600
  memory_size      = 512

  environment {
    variables = {
      AV_DEFINITION_S3_BUCKET = "${aws_s3_bucket.av_definitions_bucket.bucket}"
    }
  }
}

resource "aws_cloudwatch_event_rule" "every_3_hours" {
  name = "every-3-hours"
  schedule_expression = "rate(3 hours)"
}

resource "aws_cloudwatch_event_target" "update_av_definitions_every_3_hours" {
  rule = "${aws_cloudwatch_event_rule.every_3_hours.name}"
  target_id = "update_av_definitions"
  arn = "${aws_lambda_function.update_av_definitions.arn}"
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_upade" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.update_av_definitions.function_name}"
  principal = "events.amazonaws.com"
  source_arn = "${aws_cloudwatch_event_rule.every_3_hours.arn}"
}
