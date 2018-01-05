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

import botocore
import hashlib
import os
import pwd
import re
from common import *
from subprocess import check_output, Popen, PIPE, STDOUT


def current_library_search_path():
    ld_verbose = check_output(["ld", "--verbose"])
    rd_ld = re.compile("SEARCH_DIR\(\"([A-z0-9/-]*)\"\)")
    return rd_ld.findall(ld_verbose)


def update_defs_from_s3(bucket, prefix):
    create_dir(AV_DEFINITION_PATH)
    for filename in AV_DEFINITION_FILENAMES:
        s3_path = os.path.join(AV_DEFINITION_S3_PREFIX, filename)
        local_path = os.path.join(AV_DEFINITION_PATH, filename)
        s3_md5 = md5_from_s3_tags(bucket, s3_path)
        if os.path.exists(local_path) and md5_from_file(local_path) == s3_md5:
            print("Not downloading %s because local md5 matches s3." % filename)
            continue
        if s3_md5:
            print("Downloading definition file %s from s3://%s" % (filename, os.path.join(bucket, prefix)))
            s3.Bucket(bucket).download_file(s3_path, local_path)


def upload_defs_to_s3(bucket, prefix, local_path):
    for filename in AV_DEFINITION_FILENAMES:
        local_file_path = os.path.join(local_path, filename)
        if os.path.exists(local_file_path):
            local_file_md5 = md5_from_file(local_file_path)
            if local_file_md5 != md5_from_s3_tags(bucket, os.path.join(prefix, filename)):
                print("Uploading %s to s3://%s" % (local_file_path, os.path.join(bucket, prefix, filename)))
                s3_object = s3.Object(bucket, os.path.join(prefix, filename))
                s3_object.upload_file(os.path.join(local_path, filename))
                s3_client.put_object_tagging(
                    Bucket=s3_object.bucket_name,
                    Key=s3_object.key,
                    Tagging={"TagSet": [{"Key": "md5", "Value": local_file_md5}]}
                )
            else:
                print("Not uploading %s because md5 on remote matches local." % filename)


def update_defs_from_freshclam(path, library_path=""):
    create_dir(path)
    fc_env = os.environ.copy()
    if library_path:
        fc_env["LD_LIBRARY_PATH"] = "%s:%s" % (":".join(current_library_search_path()), CLAMAVLIB_PATH)
    print("Starting freshclam with defs in %s." % path)
    fc_proc = Popen(
        [
            FRESHCLAM_PATH,
            "--config-file=./bin/freshclam.conf",
            "-u %s" % pwd.getpwuid(os.getuid())[0],
            "--datadir=%s" % path
        ],
        stderr=STDOUT,
        stdout=PIPE,
        env=fc_env
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


def md5_from_s3_tags(bucket, key):
    try:
        tags = s3_client.get_object_tagging(Bucket=bucket, Key=key)["TagSet"]
    except botocore.exceptions.ClientError as e:
        expected_errors = {'404', 'AccessDenied', 'NoSuchKey'}
        if e.response['Error']['Code'] in expected_errors:
            return ""
        else:
            raise
    for tag in tags:
        if tag["Key"] == "md5":
            return tag["Value"]
    return ""


def scan_file(path):
    av_env = os.environ.copy()
    av_env["LD_LIBRARY_PATH"] = CLAMAVLIB_PATH
    print("Starting clamscan of %s." % path)
    av_proc = Popen(
        [
            CLAMSCAN_PATH,
            "-v",
            "-a",
            "--stdout",
            "-d",
            AV_DEFINITION_PATH,
            path
        ],
        stderr=STDOUT,
        stdout=PIPE,
        env=av_env
    )
    output = av_proc.communicate()[0]
    print("clamscan output:\n%s" % output)
    if av_proc.returncode == 0:
        return AV_STATUS_CLEAN
    elif av_proc.returncode == 1:
        return AV_STATUS_INFECTED
    else:
        msg = "Unexpected exit code from clamscan: %s.\n" % av_proc.returncode
        print(msg)
        raise Exception(msg)