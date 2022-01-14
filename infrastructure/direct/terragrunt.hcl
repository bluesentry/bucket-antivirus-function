remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }
  config = {
    bucket         = "nc-awsd-terraform-private"
    encrypt        = true
    key            = "direct/${path_relative_to_include()}/terraform.tfstate"
    region         = "us-east-1"
    profile        = "direct"
    dynamodb_table = "nc-terraform-lock-table"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
# Default AWS provider
provider "aws" {
  region              = var.aws_region
  profile             = var.aws_profile
  allowed_account_ids = [var.aws_account_id]
}

# Direct hardcoded provider
provider "aws" {
  alias               = "direct"
  region              = var.aws_region
  profile             = var.aws_profile_direct
  allowed_account_ids = [var.aws_account_id_direct]
}

# ClearData hardcoded provider
provider "aws" {
  alias               = "cleardata"
  region              = var.aws_region
  profile             = var.aws_profile_cleardata
  allowed_account_ids = [var.aws_account_id_cleardata]
}
EOF
}

inputs = merge(
  yamldecode(
    file("${find_in_parent_folders("region.yaml", "empty.yaml")}"),
  ),
  yamldecode(
    file("${find_in_parent_folders("env.yaml", "empty.yaml")}"),
  ),
  # Additional global inputs to pass to all modules called in this directory tree.
  {
    aws_account_id              = "706014839439"
    aws_account_id_cleardata    = "393224622068"
    aws_account_id_direct       = "706014839439"
    aws_profile                 = "direct"
    aws_profile_cleardata       = "cleardata"
    aws_profile_direct          = "direct"
    terraform_state_aws_profile = "direct"
    terraform_state_aws_region  = "us-east-1"
    terraform_state_s3_bucket   = "nc-awsd-terraform-private"
  },
)
