# -*- coding: utf-8 -*-
# Innerstrength Limited.
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

from pdfid import pdfid

from common import AV_SIGNATURE_OK
from common import AV_SIGNATURE_UNKNOWN
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED

def check_path(path):

    print("Screening pdf for script and automatic actions: %s" % path)
    options = pdfid.get_fake_options()
    options.scan = True
    options.json = True
    report = pdfid.PDFiDMain([path], options)["reports"][0]
    script_count=report["/JS"]+report["/JavaScript"]
    action_count=report["/AA"]+report["/OpenAction"]
    suspect_count=script_count+action_count
    print("Detected Scripts:%s Actions:%s" % (script_count,action_count))

    if suspect_count > 0:
        return AV_STATUS_INFECTED, "PDF.IllegalContent_Scripts:%s_Actions:%s" % (script_count,action_count)
    else:
        return AV_STATUS_CLEAN, AV_SIGNATURE_OK

