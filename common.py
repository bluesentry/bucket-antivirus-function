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
import os
import os.path
from distutils.util import strtobool


def create_dir(path):
    if not os.path.exists(path):
        try:
            print("Attempting to create directory %s.\n" % path)
            os.makedirs(path)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise


def get_timestamp():
    return datetime.datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC")


def str_to_bool(s):
    return bool(strtobool(str(s)))


AV_DEFINITION_S3_BUCKET = os.getenv("AV_DEFINITION_S3_BUCKET")
AV_DEFINITION_S3_PREFIX = os.getenv("AV_DEFINITION_S3_PREFIX", "clamav_defs")
AV_DEFINITION_PATH = os.getenv("AV_DEFINITION_PATH", "/tmp/clamav_defs")
AV_SCAN_START_SNS_ARN = os.getenv("AV_SCAN_START_SNS_ARN")
AV_SCAN_START_METADATA = os.getenv("AV_SCAN_START_METADATA", "av-scan-start")
AV_SIGNATURE_METADATA = os.getenv("AV_SIGNATURE_METADATA", "av-signature")
AV_SIGNATURE_OK = "OK"
AV_SIGNATURE_UNKNOWN = "UNKNOWN"
AV_STATUS_CLEAN = os.getenv("AV_STATUS_CLEAN", "CLEAN")
AV_STATUS_INFECTED = os.getenv("AV_STATUS_INFECTED", "INFECTED")
AV_STATUS_METADATA = os.getenv("AV_STATUS_METADATA", "av-status")
AV_STATUS_SNS_ARN = os.getenv("AV_STATUS_SNS_ARN")
AV_STATUS_SNS_PUBLISH_CLEAN = str_to_bool(os.getenv("AV_STATUS_SNS_PUBLISH_CLEAN", "True"))
AV_STATUS_SNS_PUBLISH_INFECTED = str_to_bool(os.getenv("AV_STATUS_SNS_PUBLISH_INFECTED", "True"))
AV_TIMESTAMP_METADATA = os.getenv("AV_TIMESTAMP_METADATA", "av-timestamp")
AV_EXTRA_VIRUS_DEFINITIONS = str_to_bool(os.getenv("AV_EXTRA_VIRUS_DEFINITIONS", "False"))
CLAMAVLIB_PATH = os.getenv("CLAMAVLIB_PATH", "./bin")
CLAMDSCAN_PATH = os.getenv("CLAMDSCAN_PATH", "./bin/clamdscan")
FRESHCLAM_PATH = os.getenv("FRESHCLAM_PATH", "./bin/freshclam")
CLAMDSCAN_TIMEOUT = os.getenv("CLAMDSCAN_TIMEOUT", 240)
CLAMD_SOCKET = os.getenv("CLAMD_SOCKET", "/tmp/clamd.sock")
AV_PROCESS_ORIGINAL_VERSION_ONLY = str_to_bool(os.getenv(
    "AV_PROCESS_ORIGINAL_VERSION_ONLY", "False"
))
AV_DELETE_INFECTED_FILES = str_to_bool(os.getenv("AV_DELETE_INFECTED_FILES", "False"))

AV_DEFINITION_FILE_PREFIXES = [
    "main",
    "daily",
    "bytecode",
]
AV_DEFINITION_FILE_SUFFIXES = ["cld", "cvd"]

AV_DEFINITION_EXTRA_FILES = [
    "MiscreantPunch099-Low.ldb",
    "badmacro.ndb",
    "blurl.ndb",
    "bofhland_cracked_URL.ndb",
    "bofhland_malware_URL.ndb",
    "bofhland_malware_attach.hdb",
    "bofhland_phishing_URL.ndb",
    "ditekshen.ldb",
    "exexor99.ldb",
    "foxhole_filename.cdb",
    "foxhole_generic.cdb",
    "foxhole_js.cdb",
    "foxhole_js.ndb",
    "hackingteam.hsb",
    "interserver256.hdb",
    "interservertopline.db",
    "junk.ndb",
    "jurlbl.ndb",
    "jurlbla.ndb",
    "lott.ndb",
    "malwarehash.hsb",
    "miscreantpunch.hdb",
    "phish.ndb",
    "phishtank.ndb",
    "porcupine.ndb",
    "rfxn.hdb",
    "rfxn.ndb",
    "rfxn.yara",
    "rogue.hdb",
    "scam.ndb",
    "shell.ldb",
    "shelter.ldb",
    "spamattach.hdb",
    "spamimg.hdb",
    "spear.ndb",
    "spearl.ndb",
    "twinclams.ldb",
    "twinwave.ign2",
    "urlhaus.ndb",
    "whitelist.fp",
    "winnow.attachments.hdb",
    "winnow_bad_cw.hdb",
    "winnow_extended_malware.hdb",
    "winnow_extended_malware_links.ndb",
    "winnow_malware.hdb",
    "winnow_malware_links.ndb",
    "winnow_phish_complete_url.ndb",
    "winnow_spam_complete.ndb"
]

SNS_ENDPOINT = os.getenv("SNS_ENDPOINT", None)
S3_ENDPOINT = os.getenv("S3_ENDPOINT", None)
LAMBDA_ENDPOINT = os.getenv("LAMBDA_ENDPOINT", None)
