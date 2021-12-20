# The AWS partition (commercial or govcloud)
data "aws_partition" "current" {}

locals {
  lambda_package_key = var.lambda_package_key != null ? var.lambda_package_key : "${var.lambda_package}/${var.lambda_version}/${var.lambda_package}.zip"
}
