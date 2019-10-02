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

import datetime
import unittest

import botocore.session
from botocore.stub import Stubber

from common import AV_STATUS_CLEAN
from common import AV_STATUS_METADATA
from common import AV_STATUS_INFECTED
from display_infected import get_objects


class TestDisplayInfected(unittest.TestCase):
    def setUp(self):
        self.s3_bucket_name = "test_bucket"
        self.s3_client = botocore.session.get_session().create_client("s3")
        self.stubber = Stubber(self.s3_client)

        list_objects_v2_response = {
            "IsTruncated": False,
            "Contents": [
                {
                    "Key": "test.txt",
                    "LastModified": datetime.datetime(2015, 1, 1),
                    "ETag": '"abc123"',
                    "Size": 123,
                    "StorageClass": "STANDARD",
                    "Owner": {"DisplayName": "myname", "ID": "abc123"},
                }
            ],
            "Name": self.s3_bucket_name,
            "Prefix": "",
            "MaxKeys": 1000,
            "EncodingType": "url",
        }
        list_objects_v2_expected_params = {"Bucket": self.s3_bucket_name}
        self.stubber.add_response(
            "list_objects_v2", list_objects_v2_response, list_objects_v2_expected_params
        )

    def test_get_objects_infected(self):

        get_object_tagging_response = {
            "VersionId": "abc123",
            "TagSet": [{"Key": AV_STATUS_METADATA, "Value": AV_STATUS_INFECTED}],
        }
        get_object_tagging_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": "test.txt",
        }
        self.stubber.add_response(
            "get_object_tagging",
            get_object_tagging_response,
            get_object_tagging_expected_params,
        )

        with self.stubber:
            s3_object_list = get_objects(self.s3_client, self.s3_bucket_name)
            expected_object_list = ["test.txt"]
            self.assertEqual(s3_object_list, expected_object_list)

    def test_get_objects_clean(self):

        get_object_tagging_response = {
            "VersionId": "abc123",
            "TagSet": [{"Key": AV_STATUS_METADATA, "Value": AV_STATUS_CLEAN}],
        }
        get_object_tagging_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": "test.txt",
        }
        self.stubber.add_response(
            "get_object_tagging",
            get_object_tagging_response,
            get_object_tagging_expected_params,
        )

        with self.stubber:
            s3_object_list = get_objects(self.s3_client, self.s3_bucket_name)
            expected_object_list = []
            self.assertEqual(s3_object_list, expected_object_list)

    def test_get_objects_unscanned(self):

        get_object_tagging_response = {"VersionId": "abc123", "TagSet": []}
        get_object_tagging_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": "test.txt",
        }
        self.stubber.add_response(
            "get_object_tagging",
            get_object_tagging_response,
            get_object_tagging_expected_params,
        )

        with self.stubber:
            s3_object_list = get_objects(self.s3_client, self.s3_bucket_name)
            expected_object_list = []
            self.assertEqual(s3_object_list, expected_object_list)
