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

from concurrent.futures.thread import ThreadPoolExecutor
import copy
import os
from distutils.util import strtobool
import shutil

import boto3

import clamav
from common import AV_DEFINITION_S3_BUCKET
from common import AV_DEFINITION_S3_PREFIX
from common import AV_SCAN_BUCKET_NAME
from common import AV_SIGNATURE_METADATA
from common import AV_SIGNATURE_OK
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED
from common import AV_STATUS_METADATA
from common import AV_TIMESTAMP_METADATA
from common import S3_ENDPOINT
from common import SQS_QUEUE_URL
from common import create_dir
from common import get_timestamp
from common import get_s3_objects_from_key_names


def lambda_handler(event, context):
    s3 = boto3.resource("s3", endpoint_url=S3_ENDPOINT)
    s3_client = boto3.client("s3", endpoint_url=S3_ENDPOINT)

    start_time = get_timestamp()
    print("Scanner starting at %s\n" % (start_time))
    # todo add multithreading to sqs receive
    s3_objects = get_objects_from_sqs(SQS_QUEUE_URL, AV_SCAN_BUCKET_NAME)
    if s3_objects is None:
        end_time = get_timestamp()
        print("Script finished at %s\n" % end_time)
        return 0

    timestamp = get_timestamp()
    print("Starting to download objects from S3 at %s\n" % timestamp)
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(download_file, s3_objects)
    timestamp = get_timestamp()
    print("Finished downloading objects from S3 at %s\n" % timestamp)

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
    print("Starting to get objects from key names for safe_objects")
    safe_objects = get_s3_objects_from_key_names(safe_files, AV_SCAN_BUCKET_NAME)
    print("Starting to get objects from key names for infected_objects")
    infected_objects = get_s3_objects_from_key_names(infected_files.keys(), AV_SCAN_BUCKET_NAME)

    result_time = get_timestamp()
    if safe_objects:
        timestamp = get_timestamp()
        print("Starting to update safe_objects tags at %s\n" % timestamp)
        with ThreadPoolExecutor(max_workers=10) as executor:
            for object in safe_objects:
                executor.submit(set_av_tags, s3_client, object, AV_STATUS_CLEAN, AV_SIGNATURE_OK, result_time)
        timestamp = get_timestamp()
        print("Finished updating safe_objects tags at %s\n" % timestamp)
    if infected_objects:
        timestamp = get_timestamp()
        print("Starting to update infected_objects tags at %s\n" % timestamp)
        with ThreadPoolExecutor(max_workers=10) as executor:
            for object in infected_objects:
                executor.submit(set_av_tags, s3_client, object, AV_STATUS_INFECTED, infected_files[object.key], result_time)
        timestamp = get_timestamp()
        print("Finished updating infected_objects tags at %s\n" % timestamp)
    # Delete downloaded files to free up room on re-usable lambda function container
    try:
        shutil.rmtree('/tmp/scandir/')
    except OSError:
        pass
    stop_scan_time = get_timestamp()
    print("Script finished at %s\n" % stop_scan_time)


def get_objects_from_sqs(queue_url, bucket_name):
    # create the client
    sqs = boto3.client('sqs')

    timestamp = get_timestamp()
    print("Starting to receive messages from SQS queue at %s\n" % timestamp)
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
    try:
        receipt_handle = response['Messages'][0]['ReceiptHandle']
        message = response['Messages'][0]['Body']
    except KeyError:
        print("No messages in queue")
        timestamp = get_timestamp()
        print("Finished receiving messages from SQS queue at %s\n" % timestamp)
        return None
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
        try:
            receipt_handle = response['Messages'][0]['ReceiptHandle']
            message = response['Messages'][0]['Body']
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
        except KeyError:
            print("No more messages in queue; exiting loop...")
            break
    timestamp = get_timestamp()
    print("Finished receiving messages from SQS queue at %s\n" % timestamp)
    all_objects = get_s3_objects_from_key_names(all_messages, bucket_name)
    return all_objects


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
    return new_tags


def str_to_bool(s):
    return bool(strtobool(str(s)))


def download_file(s3_object):
    dir_path = os.path.dirname(f'/tmp/scandir/{s3_object.key}')
    create_dir(dir_path)
    s3_object.download_file(f'/tmp/scandir/{s3_object.key}')
    # todo add error handling if the download fails
    return 0
