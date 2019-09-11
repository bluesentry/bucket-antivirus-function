#! /usr/bin/env python

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
from common import *  # noqa


# Get all objects in an S3 bucket that are infected
def get_objects(s3_bucket_name):

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
            if object_infected(s3_bucket_name, key_name):
                s3_object_list.append(key_name)

    return s3_object_list


# Determine if an object has been previously scanned for viruses
def object_infected(s3_bucket_name, key_name):
    s3_object_tags = s3_client.get_object_tagging(Bucket=s3_bucket_name, Key=key_name)
    if "TagSet" not in s3_object_tags:
        return False
    for tag in s3_object_tags["TagSet"]:
        if tag["Key"] == AV_STATUS_METADATA:
            if tag["Value"] == AV_STATUS_INFECTED:
                return True
            return False
    return False


def main(s3_bucket_name):

    # Verify the S3 bucket exists
    try:
        s3_client.head_bucket(Bucket=s3_bucket_name)
    except Exception:
        print("S3 Bucket '{}' does not exist".format(s3_bucket_name))
        sys.exit(1)

    # Scan the objects in the bucket
    s3_object_list = get_objects(s3_bucket_name)
    for key_name in s3_object_list:
        print("Infected: {}/{}".format(s3_bucket_name, key_name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scan an S3 bucket for infected files."
    )
    parser.add_argument(
        "--s3-bucket-name", required=True, help="The name of the S3 bucket to scan"
    )
    args = parser.parse_args()

    main(args.s3_bucket_name)
