terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.69"
    }
  }
  required_version = ">= 0.13.0"
}
