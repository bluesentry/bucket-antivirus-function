from common import AV_STATUS_METADATA, AV_SIGNATURE_METADATA

def sns_message_attributes(s3_object, scan_result = None, scan_signature = None):
    message_attributes = {}
    if 'sns-msg-attr-application' in s3_object.metadata:
        message_attributes['application'] = {"DataType": "String",
                                             "StringValue": s3_object.metadata['sns-msg-attr-application']}
    else:
        print("Missing attribute 'sns-msg-attr-application' from metadata")
    if 'sns-msg-attr-environment' in s3_object.metadata:
        message_attributes['environment'] = {"DataType": "String",
                                             "StringValue": s3_object.metadata['sns-msg-attr-environment']}
    else:
        print("Missing attribute 'sns-msg-attr-environment' from metadata")
    if scan_result is not None:
        message_attributes[AV_STATUS_METADATA] = {"DataType": "String",
                                                  "StringValue": scan_result}

    if scan_signature is not None:
        message_attributes[AV_SIGNATURE_METADATA] = {"DataType": "String",
                                                     "StringValue": scan_signature}
    return message_attributes