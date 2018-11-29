resource "aws_iam_role" "s3_av_scan_access" {
  name = "s3_av_scan_access"
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

resource "aws_iam_role_policy" "s3_av_scan_access_policy" {
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
            "s3:*"
         ],
         "Effect":"Allow",
         "Resource":"*"
      }
   ]
}
EOF
  role = "${aws_iam_role.s3_av_scan_access.id}"
}

resource "aws_s3_bucket" "av_target_bucket" {
  bucket = "${var.target_bucket}"
  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Action": ["s3:GetObject", "s3:PutObjectTagging"],
      "Principal": "*",
      "Resource": ["arn:aws:s3:::${var.target_bucket}/*"],
      "Condition": {
        "StringEquals": {
          "s3:ExistingObjectTag/av-status": "INFECTED"
        }
      }
    }
  ]
}
EOF
}


resource "aws_lambda_function" "scan_uploaded_file" {
  filename         = "build/lambda.zip"
  function_name    = "scan_uploaded_file"
  role             = "${aws_iam_role.s3_av_scan_access.arn}"
  source_code_hash = "${base64sha256(file("build/lambda.zip"))}"
  runtime          = "python2.7"
  handler          = "scan.lambda_handler"
  timeout          = 600
  memory_size      = 1024

  environment {
    variables = {
      AV_DEFINITION_S3_BUCKET = "${aws_s3_bucket.av_definitions_bucket.bucket}"
    }
  }
}

resource "aws_lambda_permission" "allow_bucket_event_hook" {
  statement_id  = "AllowBucketEventHook"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.scan_uploaded_file.arn}"
  principal     = "s3.amazonaws.com"
  source_arn    = "${aws_s3_bucket.av_target_bucket.arn}"
}


resource "aws_s3_bucket_notification" "scan_file_on_upload" {
  bucket = "${aws_s3_bucket.av_target_bucket.id}"

  lambda_function {
    lambda_function_arn = "${aws_lambda_function.scan_uploaded_file.arn}"
    events              = ["s3:ObjectCreated:*"]
  }
}
