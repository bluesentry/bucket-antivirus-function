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

import os
import pathlib
import unittest

import boto3
import botocore.session
from botocore.stub import Stubber

from upgrade_mime_check import is_content_type_in_static_valid_mime_list
from upgrade_mime_check import is_content_type_match_file_content

class TestScan(unittest.TestCase):
    def setUp(self):
        # Common data
        self.s3_bucket_name = "test_bucket"
        self.s3_key_name = "test_key"

        # Clients and Resources
        self.s3 = boto3.resource("s3")
        self.s3_client = botocore.session.get_session().create_client("s3")
        self.sns_client = botocore.session.get_session().create_client(
            "sns", region_name="us-west-2"
        )

        # Upgrade: specify environment and application that generate the upload url
        self.environment = "unit-test"
        self.application = "doc-mgt.srvc"

    def test_is_mime_valid_list_match(self):
        png_file = os.path.join(pathlib.Path(__file__).parent, "images", "bucket-antivirus-function.png")
        self.assertTrue(is_content_type_in_static_valid_mime_list(png_file))

    def test_is_mime_valid_list_match_invalid(self):
        python_file = os.path.join(pathlib.Path(__file__).parent, "scan.py")
        self.assertFalse(is_content_type_in_static_valid_mime_list(python_file))

    def test_is_mime_valid_content_match(self):
        s3_stubber_resource = Stubber(self.s3.meta.client)

        # First head call is done to get content type and meta data
        head_object_response = {"ContentType": "image/png", "Metadata": {}}
        head_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber_resource.add_response("head_object", head_object_response, head_object_expected_params)

        with s3_stubber_resource:
            s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
            import pathlib
            import os
            png_file = os.path.join(pathlib.Path(__file__).parent, "images", "bucket-antivirus-function.png")
            self.assertTrue(is_content_type_match_file_content(s3_obj, png_file))

    def test_is_mime_valid_content_match_invalid(self):
        s3_stubber_resource = Stubber(self.s3.meta.client)

        # First head call is done to get content type and meta data
        head_object_response = {"ContentType": "application/json", "Metadata": {}}
        head_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber_resource.add_response("head_object", head_object_response, head_object_expected_params)

        with s3_stubber_resource:
            s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
            import pathlib
            import os
            png_file = os.path.join(pathlib.Path(__file__).parent, "images", "bucket-antivirus-function.png")
            self.assertFalse(is_content_type_match_file_content(s3_obj, png_file))
