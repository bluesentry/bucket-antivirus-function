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

import boto3
import clamav
import copy
import json
import metrics
import os
from urllib.parse import unquote_plus
from distutils.util import strtobool

from common import AV_DEFINITION_S3_BUCKET
from common import AV_DEFINITION_S3_PREFIX
from common import AV_DELETE_INFECTED_FILES
from common import AV_DELETE_SNS_ARN
from common import AV_PROCESS_ORIGINAL_VERSION_ONLY
from common import AV_SCAN_ROLE_ARN
from common import AV_SCAN_SKIP_METADATA
from common import AV_SCAN_START_METADATA
from common import AV_SCAN_START_SNS_ARN
from common import AV_SIGNATURE_METADATA
from common import AV_STATUS_CLEAN
from common import AV_STATUS_CLEAN_SNS_ARN
from common import AV_STATUS_INFECTED
from common import AV_STATUS_METADATA
from common import AV_STATUS_SNS_ARN
from common import AV_STATUS_SNS_PUBLISH_CLEAN
from common import AV_STATUS_SNS_PUBLISH_INFECTED
from common import AV_TIMESTAMP_METADATA
from common import create_dir
from common import get_timestamp


def event_object(event, event_source="s3"):

    # SNS events are slightly different
    if event_source.upper() == "SNS":
        event = json.loads(event["Records"][0]["Sns"]["Message"])
    print("event_object event: %s" % event)
    # Break down the record
    records = event["Records"]
    if len(records) == 0:
        raise Exception("No records found in event!")
    record = records[0]
    print("event_object record: %s" % record)

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


# Determine if an object was safely created by a VISO process and can be ignored
def object_does_not_require_scan(s3_client, s3_bucket_name, key_name):
    s3_object_tags = s3_client.get_object_tagging(Bucket=s3_bucket_name, Key=key_name)
    if "TagSet" not in s3_object_tags:
        return False
    for tag in s3_object_tags["TagSet"]:
        if tag["Key"] == "viso:antivirus:file-source" and tag["Value"] in ["textract"]:
            return True
    return False


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


def sns_skip_scan(sns_client, s3_object, scan_skip_sns_arn, timestamp):
    message = {
        "bucket": s3_object.bucket_name,
        "key": s3_object.key,
        "version": s3_object.version_id,
        AV_SCAN_SKIP_METADATA: True,
        AV_TIMESTAMP_METADATA: timestamp,
    }
    sns_client.publish(
        TargetArn=scan_skip_sns_arn,
        Message=json.dumps({"default": json.dumps(message)}),
        MessageStructure="json",
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
    sns_client,
    s3_object,
    sns_status_arn,
    sns_clean_arn,
    scan_result,
    scan_signature,
    timestamp,
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
        TargetArn=sns_status_arn,
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
    if str_to_bool(AV_STATUS_SNS_PUBLISH_CLEAN):
        sns_client.publish(
            TargetArn=sns_clean_arn,
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


def sns_delete_results(s3_object, result):
    if AV_DELETE_INFECTED_FILES and AV_DELETE_SNS_ARN:
        message = {
            "ClamAV automation has detected an infected file was uploaded and deleted it.": {
                "bucket": s3_object.bucket_name,
                "key": s3_object.key,
                "version": s3_object.version_id,
                AV_STATUS_METADATA: result,
                AV_TIMESTAMP_METADATA: get_timestamp(),
            }
        }
        sns_client = boto3.client("sns")
        sns_client.publish(
            TargetArn=AV_DELETE_SNS_ARN,
            Message=json.dumps({"default": json.dumps(message)}),
            MessageStructure="json",
            MessageAttributes={
                AV_STATUS_METADATA: {"DataType": "String", "StringValue": result}
            },
        )


def lambda_handler(event, context):
    if AV_SCAN_ROLE_ARN:
        sts_client = boto3.client("sts")
        sts_response = sts_client.assume_role(
            RoleArn=AV_SCAN_ROLE_ARN, RoleSessionName="AVScanRoleAssumption"
        )
        session = boto3.session.Session(
            aws_access_key_id=sts_response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=sts_response["Credentials"]["SecretAccessKey"],
            aws_session_token=sts_response["Credentials"]["SessionToken"],
        )
        s3 = session.resource("s3")
        s3_client = session.client("s3")
        sns_client = session.client("sns")
    else:
        s3 = boto3.resource("s3")
        s3_client = boto3.client("s3")
        sns_client = boto3.client("sns")

    # Get some environment variables
    ENV = os.getenv("ENV", "")
    EVENT_SOURCE = os.getenv("EVENT_SOURCE", "S3")

    start_time = get_timestamp()
    print("Script starting at %s\n" % (start_time))
    print("Event received: %s" % event)
    s3_object = event_object(event, event_source=EVENT_SOURCE)

    if str_to_bool(AV_PROCESS_ORIGINAL_VERSION_ONLY):
        verify_s3_object_version(s3, s3_object)

    if object_does_not_require_scan(s3_client, s3_object.bucket_name, s3_object.key):
        sns_skip_scan(sns_client, s3_object, AV_STATUS_SNS_ARN, get_timestamp())
        print(
            "Scan of s3://%s was skipped due to the file being safely generated by a VISO process"
            % os.path.join(s3_object.bucket_name, s3_object.key)
        )
    else:
        # Publish the start time of the scan
        if AV_SCAN_START_SNS_ARN not in [None, ""]:
            start_scan_time = get_timestamp()
            sns_start_scan(
                sns_client, s3_object, AV_SCAN_START_SNS_ARN, start_scan_time
            )

        file_path = get_local_path(s3_object, "/tmp")
        create_dir(os.path.dirname(file_path))
        s3_object.download_file(file_path)

        to_download = clamav.update_defs_from_s3(
            s3_client, AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX
        )

        for download in to_download.values():
            s3_path = download["s3_path"]
            local_path = download["local_path"]
            print("Downloading definition file %s from s3://%s" % (local_path, s3_path))
            s3.Bucket(AV_DEFINITION_S3_BUCKET).download_file(s3_path, local_path)
            print("Downloading definition file %s complete!" % (local_path))
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
                AV_STATUS_CLEAN_SNS_ARN,
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
            sns_delete_results(s3_object, scan_result)
            delete_s3_object(s3_object)

    stop_scan_time = get_timestamp()
    print("Script finished at %s\n" % stop_scan_time)


def str_to_bool(s):
    return bool(strtobool(str(s)))
