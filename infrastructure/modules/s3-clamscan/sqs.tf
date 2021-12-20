resource "aws_sqs_queue" "messages" {
    name                    = "sqs-${var.env_name}-s3-antivirus-messages"
    sqs_managed_sse_enabled = true
    tags = {
        "name"      = "sqs-${var.env_name}-s3-antivirus-messages"
        "app"       = "s3-clamscan"
        "env"       = var.env_name
        "team"      = "sre"
        "sensitive" = "yes"
    }
}

resource "aws_sqs_queue_policy" "messages" {
    queue_url = aws_sqs_queue.messages.url
    policy = <<POLICY
{
  "Version": "2012-10-17",
  "Id": "sqspolicy",
  "Statement": [
    {
      "Sid": "AllowPublisherToSend",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "sqs:SendMessage",
      "Resource": "${aws_sqs_queue.messages.arn}",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "${aws_lambda_function.main_publish.arn}"
        }
      }
    },
    {
      "Sid": "AllowScannerToReceive",
      "Effect": "Allow",
      "Principal": "*",
      "Action": [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage"
      ],
      "Resource": "${aws_sqs_queue.messages.arn}",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "${aws_lambda_function.main_scan.arn}"
        }
      }
    }
  ]
}
POLICY

}