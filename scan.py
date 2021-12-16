# -*- coding: utf-8 -*-
# Upside Travel, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import copy
import json
import os
from distutils.util import strtobool
import shutil

import boto3

import clamav
from common import AV_DEFINITION_S3_BUCKET
from common import AV_DEFINITION_S3_PREFIX
from common import AV_DELETE_INFECTED_FILES
from common import AV_PROCESS_ORIGINAL_VERSION_ONLY
from common import AV_SCAN_BUCKET_NAME
from common import AV_SCAN_START_METADATA
from common import AV_SIGNATURE_METADATA
from common import AV_SIGNATURE_OK
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED
from common import AV_STATUS_METADATA
from common import AV_STATUS_SNS_PUBLISH_CLEAN
from common import AV_STATUS_SNS_PUBLISH_INFECTED
from common import AV_TIMESTAMP_METADATA
from common import S3_ENDPOINT
from common import SQS_QUEUE_URL
from common import create_dir
from common import get_timestamp
from common import get_s3_objects_from_key_names

def get_objects_from_sqs():
    # create the client
    sqs = boto3.client('sqs')
    queue_url = SQS_QUEUE_URL

    # receive first message from the queue
    all_messages = []
    response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )
    print("Response: %s\n" % response)
    try:
        receipt_handle = response['Messages'][0]['ReceiptHandle']
        message = response['Messages'][0]['Body']
    except KeyError:
        print("No messages in queue")
        return None
    print("Receipt Handle: %s\n" % receipt_handle)
    print("Message: %s\n" % message)
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle
    )

    # receive the rest of the messages from the queue
    while (len(response) > 0):
        all_messages.append(message)
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )
        print("Response: %s\n" % response)
        try:
            receipt_handle = response['Messages'][0]['ReceiptHandle']
            message = response['Messages'][0]['Body']
            print("Receipt Handle: %s\n" % receipt_handle)
            print("Message: %s\n" % message)
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
        except KeyError:
            print("No more messages in queue; exiting loop...")
            break
    all_objects = get_s3_objects_from_key_names(all_messages, AV_SCAN_BUCKET_NAME)
    return all_objects

def verify_s3_object_version(s3, s3_object):
    # validate that we only process the original version of a file, if asked to do so
    # security check to disallow processing of a new (possibly infected) object version
    # while a clean initial version is getting processed
    # downstream services may consume latest version by mistake and get the infected version instead
    bucket_versioning = s3.BucketVersioning(s3_object.bucket_name)
    if bucket_versioning.status == "Enabled":
        bucket = s3.Bucket(s3_object.bucket_name)
        versions = list(bucket.object_versions.filter(Prefix=s3_object.key))
        if len(versions) > 1:
            raise Exception(
                "Detected multiple object versions in %s.%s, aborting processing"
                % (s3_object.bucket_name, s3_object.key)
            )
    else:
        # misconfigured bucket, left with no or suspended versioning
        raise Exception(
            "Object versioning is not enabled in bucket %s" % s3_object.bucket_name
        )

def delete_s3_object(s3_object):
    try:
        s3_object.delete()
    except Exception:
        raise Exception(
            "Failed to delete infected file: %s.%s"
            % (s3_object.bucket_name, s3_object.key)
        )
    else:
        print("Infected file deleted: %s.%s" % (s3_object.bucket_name, s3_object.key))


def set_av_metadata(s3_object, scan_result, scan_signature, timestamp):
    content_type = s3_object.content_type
    metadata = s3_object.metadata
    metadata[AV_SIGNATURE_METADATA] = scan_signature
    metadata[AV_STATUS_METADATA] = scan_result
    metadata[AV_TIMESTAMP_METADATA] = timestamp
    s3_object.copy(
        {"Bucket": s3_object.bucket_name, "Key": s3_object.key},
        ExtraArgs={
            "ContentType": content_type,
            "Metadata": metadata,
            "MetadataDirective": "REPLACE",
        },
    )


def set_av_tags(s3_client, s3_object, scan_result, scan_signature, timestamp):
    curr_tags = s3_client.get_object_tagging(
        Bucket=s3_object.bucket_name, Key=s3_object.key
    )["TagSet"]
    new_tags = copy.copy(curr_tags)
    for tag in curr_tags:
        if tag["Key"] in [
            AV_SIGNATURE_METADATA,
            AV_STATUS_METADATA,
            AV_TIMESTAMP_METADATA,
        ]:
            new_tags.remove(tag)
    new_tags.append({"Key": AV_SIGNATURE_METADATA, "Value": scan_signature})
    new_tags.append({"Key": AV_STATUS_METADATA, "Value": scan_result})
    new_tags.append({"Key": AV_TIMESTAMP_METADATA, "Value": timestamp})
    s3_client.put_object_tagging(
        Bucket=s3_object.bucket_name, Key=s3_object.key, Tagging={"TagSet": new_tags}
    )


def sns_start_scan(sns_client, s3_object, scan_start_sns_arn, timestamp):
    message = {
        "bucket": s3_object.bucket_name,
        "key": s3_object.key,
        "version": s3_object.version_id,
        AV_SCAN_START_METADATA: True,
        AV_TIMESTAMP_METADATA: timestamp,
    }
    sns_client.publish(
        TargetArn=scan_start_sns_arn,
        Message=json.dumps({"default": json.dumps(message)}),
        MessageStructure="json",
    )


def sns_scan_results(
    sns_client, s3_object, sns_arn, scan_result, scan_signature, timestamp
):
    # Don't publish if scan_result is CLEAN and CLEAN results should not be published
    if scan_result == AV_STATUS_CLEAN and not str_to_bool(AV_STATUS_SNS_PUBLISH_CLEAN):
        return
    # Don't publish if scan_result is INFECTED and INFECTED results should not be published
    if scan_result == AV_STATUS_INFECTED and not str_to_bool(
        AV_STATUS_SNS_PUBLISH_INFECTED
    ):
        return
    message = {
        "bucket": s3_object.bucket_name,
        "key": s3_object.key,
        "version": s3_object.version_id,
        AV_SIGNATURE_METADATA: scan_signature,
        AV_STATUS_METADATA: scan_result,
        AV_TIMESTAMP_METADATA: get_timestamp(),
    }
    sns_client.publish(
        TargetArn=sns_arn,
        Message=json.dumps({"default": json.dumps(message)}),
        MessageStructure="json",
        MessageAttributes={
            AV_STATUS_METADATA: {"DataType": "String", "StringValue": scan_result},
            AV_SIGNATURE_METADATA: {
                "DataType": "String",
                "StringValue": scan_signature,
            },
        },
    )


def lambda_handler(event, context):
    s3 = boto3.resource("s3", endpoint_url=S3_ENDPOINT)
    s3_client = boto3.client("s3", endpoint_url=S3_ENDPOINT)

    # Get some environment variables
    ENV = os.getenv("ENV", "")

    start_time = get_timestamp()
    print("Script starting at %s\n" % (start_time))
    s3_objects = get_objects_from_sqs()
    if s3_objects == None:
        end_time = get_timestamp()
        print("Script finished at %s\n" % end_time)
        return 0

    if str_to_bool(AV_PROCESS_ORIGINAL_VERSION_ONLY):
        for s3_object in s3_objects:
            verify_s3_object_version(s3, s3_object)

    for s3_object in s3_objects:
        dir_path = os.path.dirname(f'/tmp/scandir/{s3_object.key}')
        create_dir(dir_path)
        print("Downloading object: %s\n" % s3_object.key)
        s3_object.download_file(f'{dir_path}/{s3_object.key}')

    to_download = clamav.update_defs_from_s3(
        s3_client, AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX
    )

    for download in to_download.values():
        s3_path = download["s3_path"]
        local_path = download["local_path"]
        print("Downloading definition file %s from s3://%s" % (local_path, s3_path))
        s3.Bucket(AV_DEFINITION_S3_BUCKET).download_file(s3_path, local_path)
        print("Downloading definition file %s complete!" % (local_path))

    safe_files, infected_files = clamav.scan_file('/tmp/scandir/', s3_client)
    safe_objects = get_s3_objects_from_key_names(safe_files, AV_SCAN_BUCKET_NAME)
    infected_objects = get_s3_objects_from_key_names(infected_files.keys(), AV_SCAN_BUCKET_NAME)

    result_time = get_timestamp()
    # Set the properties on the object with the scan results
    # for s3_object in s3_objects:
    #     if "AV_UPDATE_METADATA" in os.environ:
    #         set_av_metadata(s3_object, scan_result, scan_signature, result_time)
    #     set_av_tags(s3_client, s3_object, scan_result, scan_signature, result_time)
    if safe_objects:
        for object in safe_objects:
            if "AV_UPDATE_METADATA" in os.environ:
                set_av_metadata(object, AV_STATUS_CLEAN, AV_SIGNATURE_OK, result_time)
            set_av_tags(s3_client, object, AV_STATUS_CLEAN, AV_SIGNATURE_OK, result_time)
    if infected_objects:
        for object in infected_objects:
            if "AV_UPDATE_METADATA" in os.environ:
                set_av_metadata(object, AV_STATUS_INFECTED, infected_files[object.key], result_time)
            set_av_tags(s3_client, object, AV_STATUS_INFECTED, infected_files[object.key], result_time)
    # Delete downloaded files to free up room on re-usable lambda function container
    try:
        shutil.rmtree('/tmp/scandir/')
    except OSError:
        pass
    if str_to_bool(AV_DELETE_INFECTED_FILES) and infected_objects is not {}:
        for object in infected_objects:
            delete_s3_object(object)
    stop_scan_time = get_timestamp()
    print("Script finished at %s\n" % stop_scan_time)

def str_to_bool(s):
    return bool(strtobool(str(s)))
