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

from common import AV_SIGNATURE_METADATA
from common import AV_SIGNATURE_OK
from common import AV_SIGNATURE_UNKNOWN
from common import AV_STATUS_METADATA
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED


# Get all objects in an S3 bucket that are infected
def get_objects_and_sigs(s3_client, s3_bucket_name):

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
            # Include only infected objects
            infected, av_signature = object_infected(
                s3_client, s3_bucket_name, key_name
            )
            if infected:
                s3_object_list.append((key_name, av_signature))

    return s3_object_list


# Determine if an object has been previously scanned for viruses
def object_infected(s3_client, s3_bucket_name, key_name):
    s3_object_tags = s3_client.get_object_tagging(Bucket=s3_bucket_name, Key=key_name)
    if "TagSet" not in s3_object_tags:
        return False, None
    tags = {}
    for tag in s3_object_tags["TagSet"]:
        tags[tag["Key"]] = tag["Value"]

    if tags.get(AV_STATUS_METADATA, "") == AV_STATUS_CLEAN:
        return False, None

    if AV_SIGNATURE_METADATA in tags and tags[AV_SIGNATURE_METADATA] != AV_SIGNATURE_OK:
        return True, tags[AV_SIGNATURE_METADATA]

    if tags.get(AV_STATUS_METADATA, "") == AV_STATUS_INFECTED:
        return True, AV_SIGNATURE_UNKNOWN

    return False, None


def main(s3_bucket_name):

    # Verify the S3 bucket exists
    s3_client = boto3.client("s3")
    try:
        s3_client.head_bucket(Bucket=s3_bucket_name)
    except Exception:
        print("S3 Bucket '{}' does not exist".format(s3_bucket_name))
        sys.exit(1)

    # Scan the objects in the bucket
    s3_object_and_sigs_list = get_objects_and_sigs(s3_client, s3_bucket_name)
    for (key_name, av_signature) in s3_object_and_sigs_list:
        print("Infected: {}/{}, {}".format(s3_bucket_name, key_name, av_signature))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scan an S3 bucket for infected files."
    )
    parser.add_argument(
        "--s3-bucket-name", required=True, help="The name of the S3 bucket to scan"
    )
    args = parser.parse_args()

    main(args.s3_bucket_name)
