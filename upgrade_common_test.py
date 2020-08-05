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

import unittest

from upgrade_common import IS_AV_ENABLED, MIME_VALIDATION, MIME_VALIDATION_STATIC, MIME_VALIDATION_STATIC_VALID_LIST


class TestCommon(unittest.TestCase):

    def test_init_IS_AV_ENABLED(self):
        self.assertTrue(
            IS_AV_ENABLED, "Failed to get environment value IS_AV_ENABLED."
        )

    def test_init_MIME_VALIDATION(self):
        self.assertEquals(
            MIME_VALIDATION, MIME_VALIDATION_STATIC, "Failed to get environment value MIME_VALIDATION."
        )

    def test_init_MIME_VALIDATION_STATIC_VALID_LIST(self):
        self.assertEquals(
            MIME_VALIDATION_STATIC_VALID_LIST, "image/gif,image/png,image/jpeg,image/jpg,application/pdf",
            "Failed to get environment value VALID_MIMES."
        )
