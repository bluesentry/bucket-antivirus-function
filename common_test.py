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

import errno
import unittest

import mock

from common import create_dir


class TestCommon(unittest.TestCase):
    @mock.patch("common.os.path")
    @mock.patch("common.os")
    def test_create_dir_already_exists(self, mock_os, mock_path):
        mock_path.exists.return_value = True
        create_dir("testpath")
        self.assertFalse(
            mock_os.makedirs.called, "Failed to not make directories if path present."
        )

    @mock.patch("common.os.path")
    @mock.patch("common.os")
    def test_create_dir_doesnt_exist(self, mock_os, mock_path):
        mock_path.exists.return_value = False
        create_dir("testpath")
        self.assertTrue(
            mock_os.makedirs.called, "Failed to make directories if path not present."
        )

    @mock.patch("common.os.path")
    @mock.patch("common.os")
    def test_create_dir_doesnt_exist_no_raises(self, mock_os, mock_path):
        mock_path.exists.return_value = False
        mock_os.makedirs.side_effect = OSError(errno.EEXIST, "exists")
        create_dir("testpath")
        self.assertTrue(
            mock_os.makedirs.called, "Failed to make directories if path not present."
        )

    @mock.patch("common.os.path")
    @mock.patch("common.os")
    def test_create_dir_doesnt_exist_but_raises(self, mock_os, mock_path):
        mock_path.exists.return_value = False
        mock_os.makedirs.side_effect = OSError(errno.ENAMETOOLONG, "nametoolong")
        with self.assertRaises(OSError):
            create_dir("testpath")
        self.assertTrue(
            mock_os.makedirs.called, "Failed to make directories if path not present."
        )
