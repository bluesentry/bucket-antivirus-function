terraform {
  source = "../../../modules//s3-clamscan"
}

include {
  path = find_in_parent_folders()
}

inputs = {
  lambda_version = "v2.0.0"
  lambda_package = "antivirus"
  av_scan_buckets = ["dev-s3-clamscan-poc"]
}
