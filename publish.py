# -*- coding: utf-8 -*-
# Navigating Cancer, Inc.
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

from common import SQS_QUEUE_URL
from common import get_timestamp

import os
from urllib.parse import unquote_plus

import boto3

def lambda_handler(event, context):
    # get some environment variables
    EVENT_SOURCE = os.getenv("EVENT_SOURCE", "S3")

    start_time = get_timestamp()
    print("Script starting at %s\n" % (start_time))
    s3_object_key = get_keyname(event, event_source=EVENT_SOURCE)
    response = send_to_queue(s3_object_key, SQS_QUEUE_URL)
    print(response['MessageId'])

    stop_time = get_timestamp()
    print("Script finished at %s\n" % stop_time)

def get_keyname(event, event_source="s3"): # returns the name of the object that triggered this lambda
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

    # Return the key name
    print("Key Name: %s\n" % key_name)
    return key_name

def send_to_queue(message, queue_url): # sends a message to the SQS queue
    # create the client
    sqs = boto3.client('sqs')

    # send message to the queue
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=message
    )

    return response
