#! /usr/bin/env python
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

import argparse
import sys

import boto3

from common import AV_STATUS_METADATA
from common import AV_TIMESTAMP_METADATA
from common import get_timestamp


# Get all objects in an S3 bucket that have not been previously scanned
def get_objects(s3_client, s3_bucket_name):

    s3_object_list = []

    s3_list_objects_result = {"IsTruncated": True}
    while s3_list_objects_result["IsTruncated"]:
        s3_list_objects_config = {"Bucket": s3_bucket_name}
        continuation_token = s3_list_objects_result.get("NextContinuationToken")
        if continuation_token:
            s3_list_objects_config["ContinuationToken"] = continuation_token
        s3_list_objects_result = s3_client.list_objects_v2(**s3_list_objects_config)
        if "Contents" not in s3_list_objects_result:
            break
        for key in s3_list_objects_result["Contents"]:
            key_name = key["Key"]
            # Don't include objects that have been scanned
            if not object_previously_scanned(s3_client, s3_bucket_name, key_name):
                s3_object_list.append(key_name)

    return s3_object_list


# Determine if an object has been previously scanned for viruses
def object_previously_scanned(s3_client, s3_bucket_name, key_name):
    s3_object_tags = s3_client.get_object_tagging(Bucket=s3_bucket_name, Key=key_name)
    if "TagSet" not in s3_object_tags:
        return False
    for tag in s3_object_tags["TagSet"]:
        if tag["Key"] in [AV_STATUS_METADATA]:
            return True
    return False


# Tag an s3 object as clean
def tag_object(s3_client, s3_bucket_name, key_name):
    try:
        head_response = s3_client.head_object(Bucket=s3_bucket_name, Key=key_name)
        size = head_response["ContentLength"]
        if size == 0.0:
            return
        b_to_mb = 1000000
        max_size = 250 * b_to_mb
        if size > max_size:
            print(
                "Tagging: {}/{}, Size: {}".format(
                    s3_bucket_name, key_name, size / b_to_mb
                )
            )
            now = get_timestamp()
            s3_client.put_object_tagging(
                Bucket=s3_bucket_name,
                Key=key_name,
                Tagging={
                    "TagSet": [
                        {"Key": AV_STATUS_METADATA, "Value": "CLEAN"},
                        {"Key": AV_TIMESTAMP_METADATA, "Value": now},
                        {"Key": "av-notes", "Value": "MANUAL"},
                    ]
                },
            )
    except Exception as e:
        print(e)


def main(s3_bucket_name, limit):
    # Verify the S3 bucket exists
    s3_client = boto3.client("s3")
    try:
        s3_client.head_bucket(Bucket=s3_bucket_name)
    except Exception:
        print("S3 Bucket '{}' does not exist".format(s3_bucket_name))
        sys.exit(1)

    # Scan the objects in the bucket
    s3_object_list = get_objects(s3_client, s3_bucket_name)
    if limit:
        s3_object_list = s3_object_list[: min(limit, len(s3_object_list))]
    for key_name in s3_object_list:
        tag_object(s3_client, s3_bucket_name, key_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan an S3 bucket for viruses.")
    parser.add_argument(
        "--s3-bucket-name", required=True, help="The name of the S3 bucket to scan"
    )
    parser.add_argument("--limit", type=int, help="The number of records to limit to")
    args = parser.parse_args()

    main(args.s3_bucket_name, args.limit)
