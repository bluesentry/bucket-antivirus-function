variable "environment" {
  type        = string
  description = "The account this task is being created in."
}

variable "s3_bucket" {
  type        = string
  description = "S3 bucket location containing the function's deployment package"
}

variable "s3_key" {
  type        = string
  description = "S3 key of an object containing the function's deployment package"
}

variable "scanner_handler" {
  type        = string
  description = "Function entrypoint in your code"
  default     = "scan.lambda_handler"
}

variable "updater_handler" {
  type        = string
  description = "Function entrypoint in your code"
  default     = "update.lambda_handler"
}

variable "timeout" {
  type        = string
  description = "Amount of time your Lambda Function has to run in seconds"
  default     = "300"
}

variable "memory_size" {
  type        = string
  description = "Amount of memory in MB your Lambda Function can use at runtime"
  default     = "1500"
}

variable "ephemeral_storage" {
  type        = string
  description = "The size of the Lambda function Ephemeral storage(/tmp) represented in MBe"
  default     = "512"
}

variable "runtime" {
  type        = string
  description = "Identifier of the function's runtime."
  default     = "python3.7"
}

variable "definitions" {
  type        = string
  description = "S3 bucketname to store ClamAV definitions."
}

# You can add more buckets later
variable "scan_bucket_arn" {
  type        = string
  description = "A bucket arn you want to scan for malware"
}

variable "kms_key_for_scan_bucket" {
  type        = string
  description = "The KMS decryption arns if your scan buckets are encrypted"
}

variable "scan_results_topic" {
  type        = string
  description = "Name of SNS topic to send scan results to"
  default     = "s3-malware-scan-results"
}

variable "sns_subscription_endpoint" {
  type        = string
  description = "HTTPS endpoint for scan results SNS topic to send results to"
}
