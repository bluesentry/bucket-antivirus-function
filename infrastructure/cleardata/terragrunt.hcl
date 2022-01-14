remote_state {
  backend = "s3"
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite"
  }
  config = {
    bucket         = "nc-terraform-private"
    encrypt        = true
    key            = "cleardata/${path_relative_to_include()}/terraform.tfstate"
    region         = "us-east-1"
    profile        = "cleardata"
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

# ClearDATA hardcoded provider
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
  yamldecode(
    file("${find_in_parent_folders("nc_vars.yaml", "empty.yaml")}"),
  ),
  # Additional global inputs to pass to all modules called in this directory tree.
  {
    availability_zone_exclude_names = [
      "us-east-1c",
      "us-east-1e",
      "us-east-1f"
    ]
    aws_account_id              = "393224622068"
    aws_account_id_cleardata    = "393224622068"
    aws_account_id_direct       = "706014839439"
    aws_profile                 = "cleardata"
    aws_profile_cleardata       = "cleardata"
    aws_profile_direct          = "direct"
    terraform_state_aws_profile = "cleardata"
    terraform_state_aws_region  = "us-east-1"
    terraform_state_s3_bucket   = "nc-terraform-private"
  },
)
