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

import json
import unittest

import boto3

from scan import event_object


class TestScan(unittest.TestCase):
    def setUp(self):
        self.s3_bucket_name = "test_bucket"
        self.s3 = boto3.resource("s3")

    def test_sns_event_object(self):
        key_name = "key"
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": self.s3_bucket_name},
                        "object": {"key": key_name},
                    }
                }
            ]
        }
        sns_event = {"Records": [{"Sns": {"Message": json.dumps(event)}}]}
        s3_obj = event_object(sns_event, event_source="sns")
        expected_s3_object = self.s3.Object(self.s3_bucket_name, key_name)
        self.assertEquals(s3_obj, expected_s3_object)

    def test_s3_event_object(self):
        key_name = "key"
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": self.s3_bucket_name},
                        "object": {"key": key_name},
                    }
                }
            ]
        }
        s3_obj = event_object(event)
        expected_s3_object = self.s3.Object(self.s3_bucket_name, key_name)
        self.assertEquals(s3_obj, expected_s3_object)

    def test_s3_event_object_missing_bucket(self):
        key_name = "key"
        event = {"Records": [{"s3": {"object": {"key": key_name}}}]}
        with self.assertRaises(Exception) as cm:
            event_object(event)
        self.assertEquals(cm.exception.message, "No bucket found in event!")

    def test_s3_event_object_missing_key(self):
        event = {"Records": [{"s3": {"bucket": {"name": self.s3_bucket_name}}}]}
        with self.assertRaises(Exception) as cm:
            event_object(event)
        self.assertEquals(cm.exception.message, "No key found in event!")

    def test_s3_event_object_bucket_key_missing(self):
        event = {"Records": [{"s3": {"bucket": {}, "object": {}}}]}
        with self.assertRaises(Exception) as cm:
            event_object(event)
        self.assertEquals(
            cm.exception.message,
            "Unable to retrieve object from event.\n{}".format(event),
        )

    def test_s3_event_object_no_records(self):
        event = {"Records": []}
        with self.assertRaises(Exception) as cm:
            event_object(event)
        self.assertEquals(cm.exception.message, "No records found in event!")

    def test_verify_s3_object_version(self):
        pass

    def test_sns_start_scan(self):
        pass

    def test_download_s3_object(self):
        pass

    def test_set_av_metadata(self):
        pass

    def test_set_av_tags(self):
        pass

    def test_sns_scan_results(self):
        pass

    def test_delete_s3_object(self):
        pass
