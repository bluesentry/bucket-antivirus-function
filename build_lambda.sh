#!/usr/bin/env bash

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

lambda_output_file=/opt/app/build/lambda.zip

set -e

yum update -y
yum install -y cpio python2-pip yum-utils zip
yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
pip install --no-cache-dir virtualenv
virtualenv env
. env/bin/activate
# This had --no-cache-dir, tracing through multiple tickets led to a problem in wheel
pip install -r requirements.txt
rm -rf /root/.cache/pip

pushd /tmp
yumdownloader -x \*i686 --archlist=x86_64 clamav clamav-lib clamav-update json-c pcre2
rpm2cpio clamav-0*.rpm | cpio -idmv
rpm2cpio clamav-lib*.rpm | cpio -idmv
rpm2cpio clamav-update*.rpm | cpio -idmv
rpm2cpio json-c*.rpm | cpio -idmv
rpm2cpio pcre*.rpm | cpio -idmv
popd
mkdir -p bin
cp /tmp/usr/bin/clamscan /tmp/usr/bin/freshclam /tmp/usr/lib64/* bin/.
echo "DatabaseMirror database.clamav.net" > bin/freshclam.conf
echo "CompressLocalDatabase yes" >> bin/freshclam.conf

mkdir -p build
zip -r9 $lambda_output_file *.py bin
cd env/lib/python2.7/site-packages
zip -r9 $lambda_output_file *
