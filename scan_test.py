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

import unittest
import os

import boto3
import botocore.session
from botocore.stub import Stubber

from common import AV_SIGNATURE_METADATA
from common import AV_SIGNATURE_OK
from common import AV_STATUS_METADATA
from common import AV_TIMESTAMP_METADATA
from common import get_timestamp
import scan

from moto import mock_sqs
from moto import mock_s3

from publish import send_to_queue


class TestScan(unittest.TestCase):
    def setUp(self):
        # Common data
        self.s3_bucket_name = "test_bucket"
        self.s3_key_name = "test_key"

        # Clients and Resources
        self.s3 = boto3.resource("s3")
        self.s3_client = botocore.session.get_session().create_client("s3")
        self.s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)


    @mock_sqs
    def test_get_objects_from_sqs(self):
        sqs = boto3.client('sqs')
        queue = sqs.create_queue(QueueName="test-queue")
        queue_url = queue['QueueUrl']

        # Stage SQS queue with a message
        message = self.s3_key_name
        send_to_queue(message, queue_url)

        all_objects = scan.get_objects_from_sqs(queue_url, self.s3_bucket_name)
        self.assertEquals(len(all_objects), 1)
        self.assertEquals(all_objects[0], self.s3_obj)


    def test_set_av_tags(self):
        scan_result = "not_malicious"
        scan_signature = AV_SIGNATURE_OK
        timestamp = get_timestamp()
        tag_set = {
            "TagSet": [
                {"Key": "Arbitrary", "Value": "arbitrary"},
                {"Key": AV_SIGNATURE_METADATA, "Value": scan_signature},
                {"Key": AV_STATUS_METADATA, "Value": scan_result},
                {"Key": AV_TIMESTAMP_METADATA, "Value": timestamp},
            ]
        }

        s3_stubber = Stubber(self.s3_client)
        get_object_tagging_response = tag_set
        get_object_tagging_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber.add_response(
            "get_object_tagging",
            get_object_tagging_response,
            get_object_tagging_expected_params,
        )
        put_object_tagging_response = {}
        put_object_tagging_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
            "Tagging": tag_set,
        }
        s3_stubber.add_response(
            "put_object_tagging",
            put_object_tagging_response,
            put_object_tagging_expected_params,
        )

        with s3_stubber:
            response = scan.set_av_tags(self.s3_client, self.s3_obj, scan_result, scan_signature, timestamp)

        assert response == tag_set["TagSet"]


    def test_str_to_bool(self):
        string = "True"
        result = scan.str_to_bool(string)
        assert result == True


    @mock_s3
    def test_download_file(self):
        s3 = boto3.resource("s3")
        s3_client = botocore.session.get_session().create_client("s3")
        s3_client.create_bucket(Bucket=self.s3_bucket_name)
        s3_client.put_object(Bucket=self.s3_bucket_name, Key=self.s3_key_name, Body='')

        s3_obj = s3.Object(self.s3_bucket_name, self.s3_key_name)
        scan.download_file(s3_obj)
        assert os.path.isfile(f'/tmp/scandir/{s3_obj.key}')
