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
import os
import re
import textwrap
import unittest

import boto3
import botocore.session
from botocore.stub import Stubber
import mock

from clamav import RE_SEARCH_DIR
from clamav import scan_output_to_json
from clamav import md5_from_s3_tags
from clamav import time_from_s3
from clamav import update_defs_from_s3
from common import AV_DEFINITION_FILE_PREFIXES
from common import AV_DEFINITION_FILE_SUFFIXES
from common import AV_DEFINITION_S3_PREFIX
from common import AV_SIGNATURE_OK


class TestClamAV(unittest.TestCase):
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

    def test_current_library_search_path(self):
        # Calling `ld --verbose` returns a lot of text but the line to check is this one:
        search_path = """SEARCH_DIR("=/usr/x86_64-redhat-linux/lib64"); SEARCH_DIR("=/usr/lib64"); SEARCH_DIR("=/usr/local/lib64"); SEARCH_DIR("=/lib64"); SEARCH_DIR("=/usr/x86_64-redhat-linux/lib"); SEARCH_DIR("=/usr/local/lib"); SEARCH_DIR("=/lib"); SEARCH_DIR("=/usr/lib");"""  # noqa
        rd_ld = re.compile(RE_SEARCH_DIR)
        all_search_paths = rd_ld.findall(search_path)
        expected_search_paths = [
            "/usr/x86_64-redhat-linux/lib64",
            "/usr/lib64",
            "/usr/local/lib64",
            "/lib64",
            "/usr/x86_64-redhat-linux/lib",
            "/usr/local/lib",
            "/lib",
            "/usr/lib",
        ]
        self.assertEqual(all_search_paths, expected_search_paths)

    def test_scan_output_to_json_clean(self):
        file_path = "/tmp/test.txt"
        signature = AV_SIGNATURE_OK
        output = textwrap.dedent(
            """\
        Scanning {0}
        {0}: {1}
        ----------- SCAN SUMMARY -----------
        Known viruses: 6305127
        Engine version: 0.101.4
        Scanned directories: 0
        Scanned files: 1
        Infected files: 0
        Data scanned: 0.00 MB
        Data read: 0.00 MB (ratio 0.00:1)
        Time: 80.299 sec (1 m 20 s)
        """.format(
                file_path, signature
            )
        )
        summary = scan_output_to_json(output)
        self.assertEqual(summary[file_path], signature)
        self.assertEqual(summary["Infected files"], "0")

    def test_scan_output_to_json_infected(self):
        file_path = "/tmp/eicar.com.txt"
        signature = "Eicar-Test-Signature FOUND"
        output = textwrap.dedent(
            """\
        Scanning {0}
        {0}: {1}
        {0}!(0): {1}
        ----------- SCAN SUMMARY -----------
        Known viruses: 6305127
        Engine version: 0.101.4
        Scanned directories: 0
        Scanned files: 1
        Infected files: 1
        Data scanned: 0.00 MB
        Data read: 0.00 MB (ratio 0.00:1)
        Time: 80.299 sec (1 m 20 s)
        """.format(
                file_path, signature
            )
        )
        summary = scan_output_to_json(output)
        self.assertEqual(summary[file_path], signature)
        self.assertEqual(summary["Infected files"], "1")

    def test_md5_from_s3_tags_no_md5(self):
        tag_set = {"TagSet": []}

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
        with s3_stubber:
            md5_hash = md5_from_s3_tags(
                self.s3_client, self.s3_bucket_name, self.s3_key_name
            )
            self.assertEquals("", md5_hash)

    def test_md5_from_s3_tags_has_md5(self):
        expected_md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        tag_set = {"TagSet": [{"Key": "md5", "Value": expected_md5_hash}]}

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
        with s3_stubber:
            md5_hash = md5_from_s3_tags(
                self.s3_client, self.s3_bucket_name, self.s3_key_name
            )
            self.assertEquals(expected_md5_hash, md5_hash)

    def test_time_from_s3(self):

        expected_s3_time = datetime.datetime(2019, 1, 1)

        s3_stubber = Stubber(self.s3_client)
        head_object_response = {"LastModified": expected_s3_time}
        head_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber.add_response(
            "head_object", head_object_response, head_object_expected_params
        )
        with s3_stubber:
            s3_time = time_from_s3(
                self.s3_client, self.s3_bucket_name, self.s3_key_name
            )
            self.assertEquals(expected_s3_time, s3_time)

    @mock.patch("clamav.md5_from_file")
    @mock.patch("common.os.path.exists")
    def test_update_defs_from_s3(self, mock_exists, mock_md5_from_file):
        expected_md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        different_md5_hash = "d41d8cd98f00b204e9800998ecf8427f"

        mock_md5_from_file.return_value = different_md5_hash

        tag_set = {"TagSet": [{"Key": "md5", "Value": expected_md5_hash}]}
        expected_s3_time = datetime.datetime(2019, 1, 1)

        s3_stubber = Stubber(self.s3_client)

        key_names = []
        side_effect = []
        for file_prefix in AV_DEFINITION_FILE_PREFIXES:
            for file_suffix in AV_DEFINITION_FILE_SUFFIXES:
                side_effect.extend([True, True])
                filename = file_prefix + "." + file_suffix
                key_names.append(os.path.join(AV_DEFINITION_S3_PREFIX, filename))
        mock_exists.side_effect = side_effect

        for s3_key_name in key_names:
            get_object_tagging_response = tag_set
            get_object_tagging_expected_params = {
                "Bucket": self.s3_bucket_name,
                "Key": s3_key_name,
            }
            s3_stubber.add_response(
                "get_object_tagging",
                get_object_tagging_response,
                get_object_tagging_expected_params,
            )
            head_object_response = {"LastModified": expected_s3_time}
            head_object_expected_params = {
                "Bucket": self.s3_bucket_name,
                "Key": s3_key_name,
            }
            s3_stubber.add_response(
                "head_object", head_object_response, head_object_expected_params
            )

        expected_to_download = {
            "bytecode": {
                "local_path": "/tmp/clamav_defs/bytecode.cvd",
                "s3_path": "clamav_defs/bytecode.cvd",
            },
            "daily": {
                "local_path": "/tmp/clamav_defs/daily.cvd",
                "s3_path": "clamav_defs/daily.cvd",
            },
            "main": {
                "local_path": "/tmp/clamav_defs/main.cvd",
                "s3_path": "clamav_defs/main.cvd",
            },
        }
        with s3_stubber:
            to_download = update_defs_from_s3(
                self.s3_client, self.s3_bucket_name, AV_DEFINITION_S3_PREFIX
            )
            self.assertEquals(expected_to_download, to_download)

    @mock.patch("clamav.md5_from_file")
    @mock.patch("common.os.path.exists")
    def test_update_defs_from_s3_same_hash(self, mock_exists, mock_md5_from_file):
        expected_md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        different_md5_hash = expected_md5_hash

        mock_md5_from_file.return_value = different_md5_hash

        tag_set = {"TagSet": [{"Key": "md5", "Value": expected_md5_hash}]}
        expected_s3_time = datetime.datetime(2019, 1, 1)

        s3_stubber = Stubber(self.s3_client)

        key_names = []
        side_effect = []
        for file_prefix in AV_DEFINITION_FILE_PREFIXES:
            for file_suffix in AV_DEFINITION_FILE_SUFFIXES:
                side_effect.extend([True, True])
                filename = file_prefix + "." + file_suffix
                key_names.append(os.path.join(AV_DEFINITION_S3_PREFIX, filename))
        mock_exists.side_effect = side_effect

        for s3_key_name in key_names:
            get_object_tagging_response = tag_set
            get_object_tagging_expected_params = {
                "Bucket": self.s3_bucket_name,
                "Key": s3_key_name,
            }
            s3_stubber.add_response(
                "get_object_tagging",
                get_object_tagging_response,
                get_object_tagging_expected_params,
            )
            head_object_response = {"LastModified": expected_s3_time}
            head_object_expected_params = {
                "Bucket": self.s3_bucket_name,
                "Key": s3_key_name,
            }
            s3_stubber.add_response(
                "head_object", head_object_response, head_object_expected_params
            )

        expected_to_download = {}
        with s3_stubber:
            to_download = update_defs_from_s3(
                self.s3_client, self.s3_bucket_name, AV_DEFINITION_S3_PREFIX
            )
            self.assertEquals(expected_to_download, to_download)

    @mock.patch("clamav.md5_from_file")
    @mock.patch("common.os.path.exists")
    def test_update_defs_from_s3_old_files(self, mock_exists, mock_md5_from_file):
        expected_md5_hash = "d41d8cd98f00b204e9800998ecf8427e"
        different_md5_hash = "d41d8cd98f00b204e9800998ecf8427f"

        mock_md5_from_file.return_value = different_md5_hash

        tag_set = {"TagSet": [{"Key": "md5", "Value": expected_md5_hash}]}
        expected_s3_time = datetime.datetime(2019, 1, 1)

        s3_stubber = Stubber(self.s3_client)

        key_names = []
        side_effect = []
        for file_prefix in AV_DEFINITION_FILE_PREFIXES:
            for file_suffix in AV_DEFINITION_FILE_SUFFIXES:
                side_effect.extend([True, True])
                filename = file_prefix + "." + file_suffix
                key_names.append(os.path.join(AV_DEFINITION_S3_PREFIX, filename))
        mock_exists.side_effect = side_effect

        count = 0
        for s3_key_name in key_names:
            get_object_tagging_response = tag_set
            get_object_tagging_expected_params = {
                "Bucket": self.s3_bucket_name,
                "Key": s3_key_name,
            }
            s3_stubber.add_response(
                "get_object_tagging",
                get_object_tagging_response,
                get_object_tagging_expected_params,
            )
            head_object_response = {
                "LastModified": expected_s3_time - datetime.timedelta(hours=count)
            }
            head_object_expected_params = {
                "Bucket": self.s3_bucket_name,
                "Key": s3_key_name,
            }
            s3_stubber.add_response(
                "head_object", head_object_response, head_object_expected_params
            )
            count += 1

        expected_to_download = {
            "bytecode": {
                "local_path": "/tmp/clamav_defs/bytecode.cld",
                "s3_path": "clamav_defs/bytecode.cld",
            },
            "daily": {
                "local_path": "/tmp/clamav_defs/daily.cld",
                "s3_path": "clamav_defs/daily.cld",
            },
            "main": {
                "local_path": "/tmp/clamav_defs/main.cld",
                "s3_path": "clamav_defs/main.cld",
            },
        }
        with s3_stubber:
            to_download = update_defs_from_s3(
                self.s3_client, self.s3_bucket_name, AV_DEFINITION_S3_PREFIX
            )
            self.assertEquals(expected_to_download, to_download)
