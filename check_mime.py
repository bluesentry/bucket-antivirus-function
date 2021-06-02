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

import mimetypes
import magic

from common import AV_SIGNATURE_OK
from common import AV_SIGNATURE_UNKNOWN
from common import AV_STATUS_CLEAN
from common import AV_STATUS_INFECTED

KNOWN_FILE_TYPES = {
        ".mp4":  ["video/mp4","audio/mp4"],
        ".m4v":  ["video/mp4","video/x-m4v","video/m4v"],
        ".m4a":  ["audio/mp4","audio/x-m4a","audio/m4a"],
        ".mp3":  ["audio/mpeg","audio/mp3"],
        ".pdf":  ["application/pdf","application/x-pdf"],
        ".gif" : ["image/gif"],
        ".png" : ["image/png"],
        ".jpeg": ["image/jpeg"],
        ".jpg" : ["image/jpeg"],
        }

def check_path(path):

    print("Checking mimetype of %s" % path)

    extension = os.path.splitext(path)[1]

    if extension in KNOWN_FILE_TYPES:
        validMimeTypes=KNOWN_FILE_TYPES[extension]
    else:
        print("Warning: Guessing mimetypes for unknown file extension: %s" %(extension))
        # guess the mimetype based on the extension
        validMimeTypes=extensionMimeType=mimetypes.guess_type(path)

    print("Valid mimetypes for extension [%s] : %s" % (extension,validMimeTypes,))

    # detect mimetype from file using libmagic
    mime = magic.Magic(mime=True)
    mimetype = mime.from_file(path)
    print("Detected mimetype: %s" % mimetype)

    # ensure the actual file type is valis
    if mimetype in validMimeTypes:
        return AV_STATUS_CLEAN, AV_SIGNATURE_OK
    else:
        return AV_STATUS_INFECTED, "Unexpected.MimeType_" + mimetype


