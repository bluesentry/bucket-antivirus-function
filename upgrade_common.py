import os

IS_AV_ENABLED = os.getenv("IS_AV_ENABLED", "True")
MIME_VALIDATION_NONE = "no-validation"
MIME_VALIDATION_STATIC = "static"
MIME_VALIDATION_S3_CONTENT_TYPE = "s3-content-type"
MIME_VALIDATION = os.getenv("MIME_VALIDATION", MIME_VALIDATION_STATIC)
MIME_VALIDATION_STATIC_VALID_LIST = os.getenv("VALID_MIMES", "image/gif,image/png,image/jpeg,image/jpg,application/pdf")

