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

from datetime import datetime
import os

import clamav
from common import *  # noqa


def lambda_handler(event, context):
    start_time = datetime.utcnow()
    print("Script starting at %s\n" % (start_time.strftime("%Y/%m/%d %H:%M:%S UTC")))
    clamav.update_defs_from_s3(AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX)
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
        AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX, AV_DEFINITION_PATH
    )
    print(
        "Script finished at %s\n" % datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC")
    )
