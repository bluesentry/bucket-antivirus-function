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
import json
import unittest

import boto3
import botocore.session
from botocore.stub import Stubber

from common import AV_SCAN_START_METADATA
from common import AV_SIGNATURE_METADATA
from common import AV_SIGNATURE_OK
from common import AV_STATUS_METADATA
from common import AV_TIMESTAMP_METADATA
from common import get_timestamp
from scan import delete_s3_object
from scan import event_object
from scan import get_local_path
from scan import set_av_metadata
from scan import set_av_tags
from scan import sns_start_scan
from scan import sns_scan_results
from scan import verify_s3_object_version


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

    def test_sns_event_object(self):
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": self.s3_bucket_name},
                        "object": {"key": self.s3_key_name},
                    }
                }
            ]
        }
        sns_event = {"Records": [{"Sns": {"Message": json.dumps(event)}}]}
        s3_obj = event_object(sns_event, event_source="sns")
        expected_s3_object = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
        self.assertEquals(s3_obj, expected_s3_object)

    def test_s3_event_object(self):
        event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": self.s3_bucket_name},
                        "object": {"key": self.s3_key_name},
                    }
                }
            ]
        }
        s3_obj = event_object(event)
        expected_s3_object = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
        self.assertEquals(s3_obj, expected_s3_object)

    def test_s3_event_object_missing_bucket(self):
        event = {"Records": [{"s3": {"object": {"key": self.s3_key_name}}}]}
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
        s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)

        # Set up responses
        get_bucket_versioning_response = {"Status": "Enabled"}
        get_bucket_versioning_expected_params = {"Bucket": self.s3_bucket_name}
        s3_stubber_resource = Stubber(self.s3.meta.client)
        s3_stubber_resource.add_response(
            "get_bucket_versioning",
            get_bucket_versioning_response,
            get_bucket_versioning_expected_params,
        )
        list_object_versions_response = {
            "Versions": [
                {
                    "ETag": "string",
                    "Size": 123,
                    "StorageClass": "STANDARD",
                    "Key": "string",
                    "VersionId": "string",
                    "IsLatest": True,
                    "LastModified": datetime.datetime(2015, 1, 1),
                    "Owner": {"DisplayName": "string", "ID": "string"},
                }
            ]
        }
        list_object_versions_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Prefix": self.s3_key_name,
        }
        s3_stubber_resource.add_response(
            "list_object_versions",
            list_object_versions_response,
            list_object_versions_expected_params,
        )
        try:
            with s3_stubber_resource:
                verify_s3_object_version(self.s3, s3_obj)
        except Exception as e:
            self.fail("verify_s3_object_version() raised Exception unexpectedly!")
            raise e

    def test_verify_s3_object_versioning_not_enabled(self):
        s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)

        # Set up responses
        get_bucket_versioning_response = {"Status": "Disabled"}
        get_bucket_versioning_expected_params = {"Bucket": self.s3_bucket_name}
        s3_stubber_resource = Stubber(self.s3.meta.client)
        s3_stubber_resource.add_response(
            "get_bucket_versioning",
            get_bucket_versioning_response,
            get_bucket_versioning_expected_params,
        )
        with self.assertRaises(Exception) as cm:
            with s3_stubber_resource:
                verify_s3_object_version(self.s3, s3_obj)
            self.assertEquals(
                cm.exception.message,
                "Object versioning is not enabled in bucket {}".format(
                    self.s3_bucket_name
                ),
            )

    def test_verify_s3_object_version_multiple_versions(self):
        s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)

        # Set up responses
        get_bucket_versioning_response = {"Status": "Enabled"}
        get_bucket_versioning_expected_params = {"Bucket": self.s3_bucket_name}
        s3_stubber_resource = Stubber(self.s3.meta.client)
        s3_stubber_resource.add_response(
            "get_bucket_versioning",
            get_bucket_versioning_response,
            get_bucket_versioning_expected_params,
        )
        list_object_versions_response = {
            "Versions": [
                {
                    "ETag": "string",
                    "Size": 123,
                    "StorageClass": "STANDARD",
                    "Key": "string",
                    "VersionId": "string",
                    "IsLatest": True,
                    "LastModified": datetime.datetime(2015, 1, 1),
                    "Owner": {"DisplayName": "string", "ID": "string"},
                },
                {
                    "ETag": "string",
                    "Size": 123,
                    "StorageClass": "STANDARD",
                    "Key": "string",
                    "VersionId": "string",
                    "IsLatest": True,
                    "LastModified": datetime.datetime(2015, 1, 1),
                    "Owner": {"DisplayName": "string", "ID": "string"},
                },
            ]
        }
        list_object_versions_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Prefix": self.s3_key_name,
        }
        s3_stubber_resource.add_response(
            "list_object_versions",
            list_object_versions_response,
            list_object_versions_expected_params,
        )
        with self.assertRaises(Exception) as cm:
            with s3_stubber_resource:
                verify_s3_object_version(self.s3, s3_obj)
            self.assertEquals(
                cm.exception.message,
                "Detected multiple object versions in {}.{}, aborting processing".format(
                    self.s3_bucket_name, self.s3_key_name
                ),
            )

    def test_sns_start_scan(self):
        sns_stubber = Stubber(self.sns_client)
        s3_stubber_resource = Stubber(self.s3.meta.client)

        sns_arn = "some_arn"
        version_id = "version-id"
        timestamp = get_timestamp()
        message = {
            "bucket": self.s3_bucket_name,
            "key": self.s3_key_name,
            "version": version_id,
            AV_SCAN_START_METADATA: True,
            AV_TIMESTAMP_METADATA: timestamp,
        }
        publish_response = {"MessageId": "message_id"}
        publish_expected_params = {
            "TargetArn": sns_arn,
            "Message": json.dumps({"default": json.dumps(message)}),
            "MessageStructure": "json",
        }
        sns_stubber.add_response("publish", publish_response, publish_expected_params)

        head_object_response = {"VersionId": version_id}
        head_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber_resource.add_response(
            "head_object", head_object_response, head_object_expected_params
        )
        with sns_stubber, s3_stubber_resource:
            s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
            sns_start_scan(self.sns_client, s3_obj, sns_arn, timestamp)

    def test_get_local_path(self):
        local_prefix = "/tmp"

        s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
        file_path = get_local_path(s3_obj, local_prefix)
        expected_file_path = "/tmp/test_bucket/test_key"
        self.assertEquals(file_path, expected_file_path)

    def test_set_av_metadata(self):
        scan_result = "CLEAN"
        scan_signature = AV_SIGNATURE_OK
        timestamp = get_timestamp()

        s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
        s3_stubber_resource = Stubber(self.s3.meta.client)

        # First head call is done to get content type and meta data
        head_object_response = {"ContentType": "content", "Metadata": {}}
        head_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber_resource.add_response(
            "head_object", head_object_response, head_object_expected_params
        )

        # Next two calls are done when copy() is called
        head_object_response_2 = {
            "ContentType": "content",
            "Metadata": {},
            "ContentLength": 200,
        }
        head_object_expected_params_2 = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber_resource.add_response(
            "head_object", head_object_response_2, head_object_expected_params_2
        )
        copy_object_response = {"VersionId": "version_id"}
        copy_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
            "ContentType": "content",
            "CopySource": {"Bucket": self.s3_bucket_name, "Key": self.s3_key_name},
            "Metadata": {
                AV_SIGNATURE_METADATA: scan_signature,
                AV_STATUS_METADATA: scan_result,
                AV_TIMESTAMP_METADATA: timestamp,
            },
            "MetadataDirective": "REPLACE",
        }
        s3_stubber_resource.add_response(
            "copy_object", copy_object_response, copy_object_expected_params
        )

        with s3_stubber_resource:
            set_av_metadata(s3_obj, scan_result, scan_signature, timestamp)

    def test_set_av_tags(self):
        scan_result = "CLEAN"
        scan_signature = AV_SIGNATURE_OK
        timestamp = get_timestamp()
        tag_set = {
            "TagSet": [
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
            s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
            set_av_tags(self.s3_client, s3_obj, scan_result, scan_signature, timestamp)

    def test_sns_scan_results(self):
        sns_stubber = Stubber(self.sns_client)
        s3_stubber_resource = Stubber(self.s3.meta.client)

        sns_arn = "some_arn"
        version_id = "version-id"
        scan_result = "CLEAN"
        scan_signature = AV_SIGNATURE_OK
        timestamp = get_timestamp()
        message = {
            "bucket": self.s3_bucket_name,
            "key": self.s3_key_name,
            "version": version_id,
            AV_SIGNATURE_METADATA: scan_signature,
            AV_STATUS_METADATA: scan_result,
            AV_TIMESTAMP_METADATA: timestamp,
        }
        publish_response = {"MessageId": "message_id"}
        publish_expected_params = {
            "TargetArn": sns_arn,
            "Message": json.dumps({"default": json.dumps(message)}),
            "MessageAttributes": {
                "av-status": {"DataType": "String", "StringValue": scan_result},
                "av-signature": {"DataType": "String", "StringValue": scan_signature},
            },
            "MessageStructure": "json",
        }
        sns_stubber.add_response("publish", publish_response, publish_expected_params)

        head_object_response = {"VersionId": version_id}
        head_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber_resource.add_response(
            "head_object", head_object_response, head_object_expected_params
        )
        with sns_stubber, s3_stubber_resource:
            s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
            sns_scan_results(
                self.sns_client, s3_obj, sns_arn, scan_result, scan_signature, timestamp
            )

    def test_delete_s3_object(self):
        s3_stubber = Stubber(self.s3.meta.client)
        delete_object_response = {}
        delete_object_expected_params = {
            "Bucket": self.s3_bucket_name,
            "Key": self.s3_key_name,
        }
        s3_stubber.add_response(
            "delete_object", delete_object_response, delete_object_expected_params
        )

        with s3_stubber:
            s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
            delete_s3_object(s3_obj)

    def test_delete_s3_object_exception(self):
        s3_stubber = Stubber(self.s3.meta.client)

        with self.assertRaises(Exception) as cm:
            with s3_stubber:
                s3_obj = self.s3.Object(self.s3_bucket_name, self.s3_key_name)
                delete_s3_object(s3_obj)
            self.assertEquals(
                cm.exception.message,
                "Failed to delete infected file: {}.{}".format(
                    self.s3_bucket_name, self.s3_key_name
                ),
            )
