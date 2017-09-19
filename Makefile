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

AMZ_LINUX_VERSION:=latest
current_dir := $(shell pwd)
container_dir := /opt/app
circleci := ${CIRCLECI}

all: archive

clean:
	rm -rf compile/lambda.zip

archive: clean
ifeq ($(circleci), true)
	docker create -v $(container_dir) --name src alpine:3.4 /bin/true
	docker cp $(current_dir)/. src:$(container_dir)
	docker run --rm -ti \
		--volumes-from src \
		amazonlinux:$(AMZ_LINUX_VERSION) \
		/bin/bash -c "cd $(container_dir) && ./build_lambda.sh"
else
	docker run --rm -ti \
		-v $(current_dir):$(container_dir) \
		amazonlinux:$(AMZ_LINUX_VERSION) \
		/bin/bash -c "cd $(container_dir) && ./build_lambda.sh"
endif
