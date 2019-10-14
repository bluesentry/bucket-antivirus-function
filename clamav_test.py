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

import re
import textwrap
import unittest

from clamav import RE_SEARCH_DIR
from clamav import scan_output_to_json
from common import AV_SIGNATURE_OK


class TestClamAV(unittest.TestCase):
    def test_current_library_search_path(self):
        # Calling `ld --verbose` returns a lot of text but the line to check is this one:
        search_path = """SEARCH_DIR("=/usr/x86_64-redhat-linux/lib64"); SEARCH_DIR("=/usr/lib64"); SEARCH_DIR("=/usr/local/lib64"); SEARCH_DIR("=/lib64"); SEARCH_DIR("=/usr/x86_64-redhat-linux/lib"); SEARCH_DIR("=/usr/local/lib"); SEARCH_DIR("=/lib"); SEARCH_DIR("=/usr/lib");"""  # noqa
        rd_ld = re.compile(RE_SEARCH_DIR)
        all_search_paths = rd_ld.findall(search_path)
        expected_search_paths = [
            "/usr/x86_64-redhat-linux/lib64",
            "/usr/lib64",
            "/usr/local/lib64",
            "/lib64",
            "/usr/x86_64-redhat-linux/lib",
            "/usr/local/lib",
            "/lib",
            "/usr/lib",
        ]
        self.assertEqual(all_search_paths, expected_search_paths)

    def test_scan_output_to_json_clean(self):
        file_path = "/tmp/test.txt"
        signature = AV_SIGNATURE_OK
        output = textwrap.dedent(
            """\
        Scanning {0}
        {0}: {1}
        ----------- SCAN SUMMARY -----------
        Known viruses: 6305127
        Engine version: 0.101.4
        Scanned directories: 0
        Scanned files: 1
        Infected files: 0
        Data scanned: 0.00 MB
        Data read: 0.00 MB (ratio 0.00:1)
        Time: 80.299 sec (1 m 20 s)
        """.format(
                file_path, signature
            )
        )
        summary = scan_output_to_json(output)
        self.assertEqual(summary[file_path], signature)
        self.assertEqual(summary["Infected files"], "0")

    def test_scan_output_to_json_infected(self):
        file_path = "/tmp/eicar.com.txt"
        signature = "Eicar-Test-Signature FOUND"
        output = textwrap.dedent(
            """\
        Scanning {0}
        {0}: {1}
        {0}!(0): {1}
        ----------- SCAN SUMMARY -----------
        Known viruses: 6305127
        Engine version: 0.101.4
        Scanned directories: 0
        Scanned files: 1
        Infected files: 1
        Data scanned: 0.00 MB
        Data read: 0.00 MB (ratio 0.00:1)
        Time: 80.299 sec (1 m 20 s)
        """.format(
                file_path, signature
            )
        )
        summary = scan_output_to_json(output)
        self.assertEqual(summary[file_path], signature)
        self.assertEqual(summary["Infected files"], "1")
