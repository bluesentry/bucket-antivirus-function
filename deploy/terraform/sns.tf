resource "aws_sns_topic" "scan_results" {
  name = var.scan_results_topic
}

resource "aws_sns_topic_subscription" "scan_results_sub" {
  topic_arn = aws_sns_topic.scan_results.arn
  protocol  = "https"
  endpoint  = var.sns_subscription_endpoint
}
