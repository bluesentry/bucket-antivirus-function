resource "aws_lambda_function" "s3_malware_scanner" {
  function_name = "s3MalwareScanner"
  role          = aws_iam_role.s3_malware_scanner_lambda.arn
  runtime       = var.runtime
  s3_bucket     = var.s3_bucket
  s3_key        = var.s3_key
  timeout       = var.timeout
  memory_size   = var.memory_size
  handler       = var.scanner_handler

  ephemeral_storage {
    size = var.ephemeral_storage
  }

  environment {
    variables = {
      AV_DEFINITION_S3_BUCKET = "${var.environment}-${var.definitions}",
      AV_STATUS_SNS_ARN       = aws_sns_topic.scan_results.arn,
    }
  }

  depends_on = [
    aws_iam_role.s3_malware_scanner_lambda
  ]
}

resource "aws_lambda_function" "s3_malware_scanner_update_definitions" {
  function_name = "s3MalwareScannerUpdateDefinitions"
  role          = aws_iam_role.s3_malware_scanner_definitions_lambda.arn
  runtime       = var.runtime
  s3_bucket     = var.s3_bucket
  s3_key        = var.s3_key
  timeout       = var.timeout
  memory_size   = var.memory_size
  handler       = var.updater_handler


  ephemeral_storage {
    size = var.ephemeral_storage
  }

  environment {
    variables = {
      AV_DEFINITION_S3_BUCKET = "${var.environment}-${var.definitions}"
    }
  }

  depends_on = [
    aws_iam_role.s3_malware_scanner_definitions_lambda
  ]
}
