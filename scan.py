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
import signal
from urllib.parse import unquote_plus
from distutils.util import strtobool

import boto3

import clamav
import metrics
from common import AV_DEFINITION_S3_BUCKET
from common import AV_DEFINITION_S3_PREFIX
from common import AV_DELETE_INFECTED_FILES
from common import AV_PROCESS_ORIGINAL_VERSION_ONLY
from common import AV_SCAN_START_METADATA
from common import AV_SCAN_START_SNS_ARN
from common import AV_SIGNATURE_METADATA
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED
from common import AV_STATUS_METADATA
from common import AV_STATUS_SNS_ARN
from common import AV_STATUS_SNS_PUBLISH_CLEAN
from common import AV_STATUS_SNS_PUBLISH_INFECTED
from common import AV_TIMESTAMP_METADATA
from common import create_dir
from common import get_timestamp


clamd_pid = None

def event_object(event, event_source="s3"):

    # SNS events are slightly different
    if event_source.upper() == "SNS":
        event = json.loads(event["Records"][0]["Sns"]["Message"])

    # Break down the record
    records = event["Records"]
    if len(records) == 0:
        raise Exception("No records found in event!")
    record = records[0]

    s3_obj = record["s3"]

    # Get the bucket name
    if "bucket" not in s3_obj:
        raise Exception("No bucket found in event!")
    bucket_name = s3_obj["bucket"].get("name", None)

    # Get the key name
    if "object" not in s3_obj:
        raise Exception("No key found in event!")
    key_name = s3_obj["object"].get("key", None)

    if key_name:
        key_name = unquote_plus(key_name)

    # Ensure both bucket and key exist
    if (not bucket_name) or (not key_name):
        raise Exception("Unable to retrieve object from event.\n{}".format(event))

    # Create and return the object
    s3 = boto3.resource("s3")
    return s3.Object(bucket_name, key_name)


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


def get_local_path(s3_object, local_prefix):
    return os.path.join(local_prefix, s3_object.bucket_name, s3_object.key)


def delete_s3_object(s3_object):
    try:
        s3_object.delete()
    except Exception:
        raise Exception(
            "Failed to delete infected file: %s.%s"
            % (s3_object.bucket_name, s3_object.key)
        )
    else:
        print("Infected file deleted: %s" % os.path.join("s3://", s3_object.bucket_name, s3_object.key))


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


def kill_process_by_pid(pid):
    # Check if process is running on PID
    try:
        os.kill(clamd_pid, 0)
    except OSError:
        return

    print("Killing the process by PID %s" % clamd_pid)

    try:
        os.kill(clamd_pid, signal.SIGTERM)
    except OSError:
        os.kill(clamd_pid, signal.SIGKILL)


def lambda_handler(event, context):
    global clamd_pid

    s3 = boto3.resource("s3")
    s3_client = boto3.client("s3")
    sns_client = boto3.client("sns")

    # Get some environment variables
    ENV = os.getenv("ENV", "")
    EVENT_SOURCE = os.getenv("EVENT_SOURCE", "S3")

    if not clamav.is_clamd_running():
        if clamd_pid is not None:
            kill_process_by_pid(clamd_pid)

        clamd_pid = clamav.start_clamd_daemon()
        print("Clamd PID: %s" % clamd_pid)

    start_time = get_timestamp()
    print("Script starting at %s\n" % (start_time))
    s3_object = event_object(event, event_source=EVENT_SOURCE)

    if str_to_bool(AV_PROCESS_ORIGINAL_VERSION_ONLY):
        verify_s3_object_version(s3, s3_object)

    # Publish the start time of the scan
    if AV_SCAN_START_SNS_ARN not in [None, ""]:
        start_scan_time = get_timestamp()
        sns_start_scan(sns_client, s3_object, AV_SCAN_START_SNS_ARN, start_scan_time)

    file_path = get_local_path(s3_object, "/tmp")
    create_dir(os.path.dirname(file_path))
    s3_object.download_file(file_path)

    scan_result, scan_signature = clamav.scan_file(file_path)
    print(
        "Scan of s3://%s resulted in %s\n"
        % (os.path.join(s3_object.bucket_name, s3_object.key), scan_result)
    )

    result_time = get_timestamp()
    # Set the properties on the object with the scan results
    if "AV_UPDATE_METADATA" in os.environ:
        set_av_metadata(s3_object, scan_result, scan_signature, result_time)
    set_av_tags(s3_client, s3_object, scan_result, scan_signature, result_time)

    # Publish the scan results
    if AV_STATUS_SNS_ARN not in [None, ""]:
        sns_scan_results(
            sns_client,
            s3_object,
            AV_STATUS_SNS_ARN,
            scan_result,
            scan_signature,
            result_time,
        )

    metrics.send(
        env=ENV, bucket=s3_object.bucket_name, key=s3_object.key, status=scan_result
    )
    # Delete downloaded file to free up room on re-usable lambda function container
    try:
        os.remove(file_path)
    except OSError:
        pass
    if str_to_bool(AV_DELETE_INFECTED_FILES) and scan_result == AV_STATUS_INFECTED:
        delete_s3_object(s3_object)
    stop_scan_time = get_timestamp()
    print("Script finished at %s\n" % stop_scan_time)


def str_to_bool(s):
    return bool(strtobool(str(s)))
