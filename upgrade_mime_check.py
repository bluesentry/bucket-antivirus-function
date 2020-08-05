import magic

from upgrade_common import MIME_VALIDATION, MIME_VALIDATION_S3_CONTENT_TYPE, MIME_VALIDATION_STATIC, \
    MIME_VALIDATION_STATIC_VALID_LIST


def is_content_type_match_file_content(s3_object, file_path):
    content_type = magic.from_file(file_path, mime=True)
    print("comparing s3_content_type=[%s] vs magic_content_type=[%s]" % (s3_object.content_type, content_type))
    return content_type is not None and content_type == s3_object.content_type


def is_content_type_in_static_valid_mime_list(file_path):
    content_type = magic.from_file(file_path, mime=True)
    print("Verifying content_type=[%s] against static list of [%s]" % (content_type, MIME_VALIDATION_STATIC_VALID_LIST))
    return content_type is not None and content_type in MIME_VALIDATION_STATIC_VALID_LIST.split(",")


def is_mime_valid(s3_object, file_path):
    if MIME_VALIDATION == MIME_VALIDATION_S3_CONTENT_TYPE:
        return is_content_type_match_file_content(s3_object, file_path)
    if MIME_VALIDATION == MIME_VALIDATION_STATIC:
        return is_content_type_in_static_valid_mime_list(file_path)

    print("MIME Validation is not enabled returning True")
    return True
