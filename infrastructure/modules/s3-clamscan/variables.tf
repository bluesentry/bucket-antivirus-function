variable "aws_region" {
  description = "The AWS region in which all resources will be created."
  type        = string
}

variable "aws_profile" {
  description = "The name of the AWS profile used to create resources"
  type        = string
}

variable "aws_account_id" {
  description = "The ID of the AWS Account in which to create resources"
  type        = string
}

variable "env_name" {
  description = "Name of environment, used for tagging and naming."
  type        = string
}

variable "cloudwatch_logs_retention_days" {
  default     = "2"
  description = "Number of days to keep logs in AWS CloudWatch."
  type        = string
}

variable "lambda_version" {
  description = "The version the Lambda function to deploy."
  type        = string
}

variable "lambda_package" {
  description = "The name of the lambda package. Used for a directory tree and zip file."
  type        = string
}

variable "lambda_package_key" {
  description = "The object key for the lambda distribution. If given, the value is used as the key in lieu of the value constructed using `lambda_package` and `lambda_version`."
  type        = string
  default     = null
}

variable "scanner_memory_size" {
  description = "Memory allocation for Scanner Lambda, in MB"
  type        = number
  default     = 2048
}

variable "updater_memory_size" {
  description = "Memory allocation for Updater Lambda, in MB"
  type        = number
  default     = 2048
}

variable "publisher_memory_size" {
  description = "Memory allocation for Publisher Lambda, in MB"
  type        = number
  default     = 128
}

variable "av_update_minutes" {
  default     = 180
  description = "How often to download updated AV signatures."
  type        = number
}

variable "av_scan_buckets" {
  description = "A list of S3 bucket names to scan for viruses."
  type        = list(string)
}

variable "timeout_seconds" {
  description = "Lambda timeout, in seconds"
  type        = number
  default     = 300
}

variable "av_scan_minutes" {
  description = "How often to trigger the scanner Lambda."
  default     = 1
  type        = number
}
