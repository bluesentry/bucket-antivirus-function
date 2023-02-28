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
import subprocess

import boto3

import clamav
from common import AV_DEFINITION_PATH
from common import AV_DEFINITION_EXTRA_PATH
from common import AV_DEFINITION_S3_BUCKET
from common import AV_DEFINITION_S3_PREFIX
from common import AV_DEFINITION_S3_EXTRA_PREFIX
from common import AV_USE_FANGFRISCH
from common import CLAMAVLIB_PATH
from common import S3_ENDPOINT
from common import get_timestamp


def lambda_handler(event, context):
    s3 = boto3.resource("s3", endpoint_url=S3_ENDPOINT)
    s3_client = boto3.client("s3", endpoint_url=S3_ENDPOINT)

    print("Script starting at %s\n" % (get_timestamp()))
    to_download = clamav.update_defs_from_s3(
        s3_client, AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX
    )

    for download in to_download.values():
        s3_path = download["s3_path"]
        local_path = download["local_path"]
        print("Downloading definition file %s from s3://%s" % (local_path, s3_path))
        s3.Bucket(AV_DEFINITION_S3_BUCKET).download_file(s3_path, local_path)
        print("Downloading definition file %s complete!" % (local_path))

    if AV_USE_FANGFRISCH:
        env_with_pythonpath = os.environ.copy()
        env_with_pythonpath["PYTHONPATH"] = env_with_pythonpath["LAMBDA_TASK_ROOT"]
        bucket_extra_defs_path = os.path.join("s3://", AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_EXTRA_PREFIX)
        sync_command = f"bin/aws s3 sync {bucket_extra_defs_path} {AV_DEFINITION_EXTRA_PATH}"
        subprocess.run(sync_command, shell=True, env=env_with_pythonpath)

        fangfrisch_base_command = "bin/fangfrisch --conf fangfrisch.conf"
        subprocess.run(f"{fangfrisch_base_command} initdb", shell=True, env=env_with_pythonpath)
        subprocess.run(f"{fangfrisch_base_command} refresh", shell=True, env=env_with_pythonpath)

        sync_after_command = f"bin/aws s3 sync {AV_DEFINITION_EXTRA_PATH} {bucket_extra_defs_path}"
        subprocess.run(sync_after_command, shell=True, env=env_with_pythonpath)
    else:
        print("Skip downloading extra virus definitions with Fangfrisch")

    clamav.update_defs_from_freshclam(AV_DEFINITION_PATH, CLAMAVLIB_PATH)
    # If main.cvd gets updated (very rare), we will need to force freshclam
    # to download the compressed version to keep file sizes down.
    # The existence of main.cud is the trigger to know this has happened.
    if os.path.exists(os.path.join(AV_DEFINITION_PATH, "main.cud")):
        os.remove(os.path.join(AV_DEFINITION_PATH, "main.cud"))
        if os.path.exists(os.path.join(AV_DEFINITION_PATH, "main.cvd")):
            os.remove(os.path.join(AV_DEFINITION_PATH, "main.cvd"))
        clamav.update_defs_from_freshclam(AV_DEFINITION_PATH, CLAMAVLIB_PATH)
    clamav.upload_defs_to_s3(
        s3_client, AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX, AV_DEFINITION_PATH
    )
    print("Script finished at %s\n" % get_timestamp())
