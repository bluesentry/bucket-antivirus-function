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
import hashlib
import os
import pwd
import re
import subprocess

import boto3
import botocore
from pytz import utc

from common import AV_DEFINITION_S3_PREFIX
from common import AV_DEFINITION_PATH
from common import AV_DEFINITION_FILE_PREFIXES
from common import AV_DEFINITION_FILE_SUFFIXES
from common import AV_SIGNATURE_OK
from common import AV_SIGNATURE_UNKNOWN
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED
from common import CLAMAVLIB_PATH
from common import CLAMSCAN_PATH
from common import FRESHCLAM_PATH
from common import create_dir


RE_SEARCH_DIR = r"SEARCH_DIR\(\"=([A-z0-9\/\-_]*)\"\)"


def current_library_search_path():
    ld_verbose = subprocess.check_output(["ld", "--verbose"]).decode("utf-8")
    rd_ld = re.compile(RE_SEARCH_DIR)
    return rd_ld.findall(ld_verbose)


def update_defs_from_s3(s3_client, bucket, prefix):
    create_dir(AV_DEFINITION_PATH)
    to_download = {}
    for file_prefix in AV_DEFINITION_FILE_PREFIXES:
        s3_best_time = None
        for file_suffix in AV_DEFINITION_FILE_SUFFIXES:
            filename = file_prefix + "." + file_suffix
            s3_path = os.path.join(AV_DEFINITION_S3_PREFIX, filename)
            local_path = os.path.join(AV_DEFINITION_PATH, filename)
            s3_md5 = md5_from_s3_tags(s3_client, bucket, s3_path)
            s3_time = time_from_s3(s3_client, bucket, s3_path)

            if s3_best_time is not None and s3_time < s3_best_time:
                print("Not downloading older file in series: %s" % filename)
                continue
            else:
                s3_best_time = s3_time

            if os.path.exists(local_path) and md5_from_file(local_path) == s3_md5:
                print("Not downloading %s because local md5 matches s3." % filename)
                continue
            if s3_md5:
                to_download[file_prefix] = {
                    "s3_path": s3_path,
                    "local_path": local_path,
                }
    return to_download


def upload_defs_to_s3(s3_client, bucket, prefix, local_path):
    for file_prefix in AV_DEFINITION_FILE_PREFIXES:
        for file_suffix in AV_DEFINITION_FILE_SUFFIXES:
            filename = file_prefix + "." + file_suffix
            local_file_path = os.path.join(local_path, filename)
            if os.path.exists(local_file_path):
                local_file_md5 = md5_from_file(local_file_path)
                if local_file_md5 != md5_from_s3_tags(
                    s3_client, bucket, os.path.join(prefix, filename)
                ):
                    print(
                        "Uploading %s to s3://%s"
                        % (local_file_path, os.path.join(bucket, prefix, filename))
                    )
                    s3 = boto3.resource("s3")
                    s3_object = s3.Object(bucket, os.path.join(prefix, filename))
                    s3_object.upload_file(os.path.join(local_path, filename))
                    s3_client.put_object_tagging(
                        Bucket=s3_object.bucket_name,
                        Key=s3_object.key,
                        Tagging={"TagSet": [{"Key": "md5", "Value": local_file_md5}]},
                    )
                else:
                    print(
                        "Not uploading %s because md5 on remote matches local."
                        % filename
                    )
            else:
                print("File does not exist: %s" % filename)


def update_defs_from_freshclam(path, library_path=""):
    create_dir(path)
    fc_env = os.environ.copy()
    if library_path:
        fc_env["LD_LIBRARY_PATH"] = "%s:%s" % (
            ":".join(current_library_search_path()),
            CLAMAVLIB_PATH,
        )
    print("Starting freshclam with defs in %s." % path)
    fc_proc = subprocess.Popen(
        [
            FRESHCLAM_PATH,
            "--config-file=./bin/freshclam.conf",
            "-u %s" % pwd.getpwuid(os.getuid())[0],
            "--datadir=%s" % path,
        ],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        env=fc_env,
    )
    output = fc_proc.communicate()[0]
    print("freshclam output:\n%s" % output)
    if fc_proc.returncode != 0:
        print("Unexpected exit code from freshclam: %s." % fc_proc.returncode)
    return fc_proc.returncode


def md5_from_file(filename):
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def md5_from_s3_tags(s3_client, bucket, key):
    try:
        tags = s3_client.get_object_tagging(Bucket=bucket, Key=key)["TagSet"]
    except botocore.exceptions.ClientError as e:
        expected_errors = {
            "404",  # Object does not exist
            "AccessDenied",  # Object cannot be accessed
            "NoSuchKey",  # Object does not exist
            "MethodNotAllowed",  # Object deleted in bucket with versioning
        }
        if e.response["Error"]["Code"] in expected_errors:
            return ""
        else:
            raise
    for tag in tags:
        if tag["Key"] == "md5":
            return tag["Value"]
    return ""


def time_from_s3(s3_client, bucket, key):
    try:
        time = s3_client.head_object(Bucket=bucket, Key=key)["LastModified"]
    except botocore.exceptions.ClientError as e:
        expected_errors = {"404", "AccessDenied", "NoSuchKey"}
        if e.response["Error"]["Code"] in expected_errors:
            return datetime.datetime.fromtimestamp(0, utc)
        else:
            raise
    return time


# Turn ClamAV Scan output into a JSON formatted data object
def scan_output_to_json(output):
    summary = {}
    for line in output.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            summary[key] = value.strip()
    return summary


def scan_file(path):
    av_env = os.environ.copy()
    av_env["LD_LIBRARY_PATH"] = CLAMAVLIB_PATH
    print("Starting clamscan of %s." % path)
    av_proc = subprocess.Popen(
        [CLAMSCAN_PATH, "-v", "-a", "--stdout", "-d", AV_DEFINITION_PATH, path],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        env=av_env,
    )
    output = av_proc.communicate()[0].decode()
    print("clamscan output:\n%s" % output)

    # Turn the output into a data source we can read
    summary = scan_output_to_json(output)
    if av_proc.returncode == 0:
        return AV_STATUS_CLEAN, AV_SIGNATURE_OK
    elif av_proc.returncode == 1:
        signature = summary.get(path, AV_SIGNATURE_UNKNOWN)
        return AV_STATUS_INFECTED, signature
    else:
        msg = "Unexpected exit code from clamscan: %s.\n" % av_proc.returncode
        print(msg)
        raise Exception(msg)
