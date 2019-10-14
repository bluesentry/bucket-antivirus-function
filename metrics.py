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

import datadog
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED


def send(env, bucket, key, status):
    if "DATADOG_API_KEY" in os.environ:
        datadog.initialize()  # by default uses DATADOG_API_KEY

        result_metric_name = "unknown"

        metric_tags = ["env:%s" % env, "bucket:%s" % bucket, "object:%s" % key]

        if status == AV_STATUS_CLEAN:
            result_metric_name = "clean"
        elif status == AV_STATUS_INFECTED:
            result_metric_name = "infected"
            datadog.api.Event.create(
                title="Infected S3 Object Found",
                text="Virus found in s3://%s/%s." % (bucket, key),
                tags=metric_tags,
            )

        scanned_metric = {
            "metric": "s3_antivirus.scanned",
            "type": "counter",
            "points": 1,
            "tags": metric_tags,
        }
        result_metric = {
            "metric": "s3_antivirus.%s" % result_metric_name,
            "type": "counter",
            "points": 1,
            "tags": metric_tags,
        }
        print("Sending metrics to Datadog.")
        datadog.api.Metric.send([scanned_metric, result_metric])
