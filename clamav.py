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
import errno
import hashlib
import json
import os
import pwd
import re
import socket
import subprocess

import boto3
import botocore
from pytz import utc

from common import AV_DEFINITION_FILE_PREFIXES
from common import AV_DEFINITION_FILE_SUFFIXES
from common import AV_DEFINITION_PATH
from common import AV_DEFINITION_S3_BUCKET
from common import AV_DEFINITION_S3_PREFIX
from common import AV_DEFINITION_EXTRA_FILES
from common import AV_EXTRA_VIRUS_DEFINITIONS
from common import AV_SIGNATURE_OK
from common import AV_SIGNATURE_UNKNOWN
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED
from common import CLAMAVLIB_PATH
from common import CLAMDSCAN_PATH
from common import CLAMDSCAN_TIMEOUT
from common import CLAMD_SOCKET
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
    older_files = set()
    md5_matches = set()
    for file_prefix in AV_DEFINITION_FILE_PREFIXES:
        s3_best_time = None
        for file_suffix in AV_DEFINITION_FILE_SUFFIXES:
            filename = file_prefix + "." + file_suffix
            s3_path = os.path.join(AV_DEFINITION_S3_PREFIX, filename)
            local_path = os.path.join(AV_DEFINITION_PATH, filename)
            s3_md5 = md5_from_s3_tags(s3_client, bucket, s3_path)
            s3_time = time_from_s3(s3_client, bucket, s3_path)

            if s3_best_time is not None and s3_time < s3_best_time:
                older_files.add(filename)
                continue
            else:
                s3_best_time = s3_time

            if os.path.exists(local_path) and md5_from_file(local_path) == s3_md5:
                md5_matches.add(filename)
                continue
            if s3_md5:
                to_download[file_prefix] = {
                    "s3_path": s3_path,
                    "local_path": local_path,
                }

    if AV_EXTRA_VIRUS_DEFINITIONS is True:
        for filename in AV_DEFINITION_EXTRA_FILES:
            s3_path = os.path.join(AV_DEFINITION_S3_PREFIX, filename)
            local_path = os.path.join(AV_DEFINITION_PATH, filename)
            s3_md5 = md5_from_s3_tags(s3_client, bucket, s3_path)
            if os.path.exists(local_path) and md5_from_file(local_path) == s3_md5:
                md5_matches.add(filename)
                continue
            if s3_md5:
                to_download[filename] = {
                    "s3_path": s3_path,
                    "local_path": local_path,
                }

    if older_files:
        print("Not downloading the following older files in series:")
        print(json.dumps(list(older_files)))
    if md5_matches:
        print("Not downloading the following files because local md5 matches s3:")
        print(json.dumps(list(md5_matches)))
    return to_download


class Md5Matches(Exception):
    pass


class NoSuchFile(Exception):
    pass


def upload_defs_to_s3(s3_client, bucket, prefix, local_path):
    md5_matches = set()
    non_existent_files = set()
    official_databases = [file_prefix + "." + file_suffix
                          for file_prefix in AV_DEFINITION_FILE_PREFIXES
                          for file_suffix in AV_DEFINITION_FILE_SUFFIXES]
    all_databases = (official_databases + AV_DEFINITION_EXTRA_FILES
                     if AV_EXTRA_VIRUS_DEFINITIONS is True
                     else official_databases)

    for filename in all_databases:
        try:
            upload_new_file_to_s3(bucket, filename, local_path, prefix, s3_client)
        except Md5Matches:
            md5_matches.add(filename)
        except NoSuchFile:
            non_existent_files.add(filename)

    if non_existent_files:
        print("The following files do not exist for upload:")
        print(json.dumps(list(non_existent_files)))
    if md5_matches:
        print("The following MD5 hashes match those in S3:")
        print(json.dumps(list(md5_matches)))


def upload_new_file_to_s3(bucket, filename, local_path, prefix, s3_client):
    local_file_path = os.path.join(local_path, filename)

    if not os.path.exists(local_file_path):
        raise NoSuchFile

    local_file_md5 = md5_from_file(local_file_path)

    if local_file_md5 == md5_from_s3_tags(s3_client, bucket, os.path.join(prefix, filename)):
        raise Md5Matches

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
            "--config-file=%s/freshclam.conf" % CLAMAVLIB_PATH,
            "-u %s" % pwd.getpwuid(os.getuid())[0],
            "--datadir=%s" % path,
        ],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        env=fc_env,
    )
    output = fc_proc.communicate()[0].decode()
    print("freshclam output:")
    print(json.dumps(output.split("\n")))
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
    print("Starting clamdscan of %s." % path)
    av_proc = subprocess.Popen(
        [
            CLAMDSCAN_PATH,
            "-v",
            "--stdout",
            "--config-file",
            "%s/scan.conf" % CLAMAVLIB_PATH,
            path,
        ],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        env=av_env,
    )

    try:
        output, errors = av_proc.communicate(timeout=CLAMDSCAN_TIMEOUT)
    except subprocess.TimeoutExpired:
        av_proc.kill()
        output, errors = av_proc.communicate()

    decoded_output = output.decode()
    print("clamdscan output:\n%s" % decoded_output)

    if av_proc.returncode == 0:
        return AV_STATUS_CLEAN, AV_SIGNATURE_OK
    elif av_proc.returncode == 1:
        # Turn the output into a data source we can read
        summary = scan_output_to_json(decoded_output)
        signature = summary.get(path, AV_SIGNATURE_UNKNOWN)
        return AV_STATUS_INFECTED, signature
    else:
        msg = "Unexpected exit code from clamdscan: %s.\n" % av_proc.returncode

        if errors:
            msg += "Errors: %s\n" % errors.decode()

        print(msg)
        raise Exception(msg)


def is_clamd_running():
    print("Checking if clamd is running on %s" % CLAMD_SOCKET)

    if os.path.exists(CLAMD_SOCKET):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect(CLAMD_SOCKET)
            s.send(b"PING")
            try:
                data = s.recv(32)
            except (socket.timeout, socket.error) as e:
                print("Failed to read from socket: %s\n" % e)
                return False

        print("Received %s in response to PING" % repr(data))
        return data == b"PONG\n"

    print("Clamd is not running on %s" % CLAMD_SOCKET)
    return False


def start_clamd_daemon():
    s3 = boto3.resource("s3")
    s3_client = boto3.client("s3")

    to_download = update_defs_from_s3(
        s3_client, AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX
    )

    for download in to_download.values():
        s3_path = download["s3_path"]
        local_path = download["local_path"]
        print("Downloading definition file %s from s3://%s" % (local_path, s3_path))
        s3.Bucket(AV_DEFINITION_S3_BUCKET).download_file(s3_path, local_path)
        print("Downloading definition file %s complete!" % (local_path))

    av_env = os.environ.copy()
    av_env["LD_LIBRARY_PATH"] = CLAMAVLIB_PATH

    print("Starting clamd")

    if os.path.exists(CLAMD_SOCKET):
        try:
            os.unlink(CLAMD_SOCKET)
        except OSError as e:
            if e.errno != errno.ENOENT:
                print("Could not unlink clamd socket %s" % CLAMD_SOCKET)
                raise

    clamd_proc = subprocess.Popen(
        ["%s/clamd" % CLAMAVLIB_PATH, "-c", "%s/scan.conf" % CLAMAVLIB_PATH],
        env=av_env,
    )

    clamd_proc.wait()

    clamd_log_file = open("/tmp/clamd.log")
    print(clamd_log_file.read())

    return clamd_proc.pid
