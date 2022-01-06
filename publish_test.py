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

import unittest

import publish


class TestScan(unittest.TestCase):
    def test_get_keyname_no_records(self):
        event_source = "S3"
        event = {"Records": {}}
        with self.assertRaises(Exception) as context:
            publish.get_keyname(event, event_source)
        self.assertTrue("No records found in event!" in str(context.exception))

    def test_get_keyname_no_bucket(self):
        event_source = "S3"
        event = {"Records": [{"s3": {"object": {"key": "test/key"}}}]}
        with self.assertRaises(Exception) as context:
            publish.get_keyname(event, event_source)
        self.assertTrue("No bucket found in event!" in str(context.exception))

    def test_get_keyname_no_key(self):
        event_source = "S3"
        event = {"Records": [{"s3": {"bucket": {"name": "test-bucket"}}}]}
        with self.assertRaises(Exception) as context:
            publish.get_keyname(event, event_source)
        self.assertTrue("No key found in event!" in str(context.exception))

    def test_get_keyname_no_bucket_name(self):
        event_source = "S3"
        event = {"Records": [{"s3": {"bucket": {}, "object": {"key": "test/key"}}}]}
        with self.assertRaises(Exception) as context:
            publish.get_keyname(event, event_source)
        self.assertTrue(
            "Unable to retrieve object from event." in str(context.exception)
        )

    def test_get_keyname_no_key_name(self):
        event_source = "S3"
        event = {"Records": [{"s3": {"bucket": {"name": "test-bucket"}, "object": {}}}]}
        with self.assertRaises(Exception) as context:
            publish.get_keyname(event, event_source)
        self.assertTrue(
            "Unable to retrieve object from event." in str(context.exception)
        )

    def test_get_keyname(self):
        event_source = "S3"
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "test/key"},
                    }
                }
            ]
        }
        key_name = publish.get_keyname(event, event_source)
        self.assertTrue(key_name in "test/key")
