# 1. Upload the av.zip artifact from build to s3 first.
# 2. Enter your terraform backend info here

provider "aws" {
  region = ""
}

terraform {
  backend "s3" {
    bucket         = ""
    region         = ""
    key            = "terraform.tfstate"
  }
}
