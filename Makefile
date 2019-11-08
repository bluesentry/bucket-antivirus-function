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

AMZ_LINUX_VERSION:=2
current_dir := $(shell pwd)
container_dir := /opt/app
circleci := ${CIRCLECI}

.PHONY: help
help:  ## Print the help documentation
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

all: archive  ## Build the entire project

.PHONY: clean
clean:  ## Clean build artifacts
	rm -rf bin/
	rm -rf build/
	rm -rf tmp/
	rm -f .coverage
	find ./ -type d -name '__pycache__' -delete
	find ./ -type f -name '*.pyc' -delete

.PHONY: archive
archive: clean  ## Create the archive for AWS lambda
	docker build -t bucket-antivirus-function:latest .
	mkdir -p ./build/
	docker run -v $(current_dir)/build:/opt/mount --rm --entrypoint cp bucket-antivirus-function:latest /opt/app/build/lambda.zip /opt/mount/lambda.zip

.PHONY: pre_commit_install  ## Ensure that pre-commit hook is installed and kept up to date
pre_commit_install: .git/hooks/pre-commit ## Ensure pre-commit is installed
.git/hooks/pre-commit: /usr/local/bin/pre-commit
	pip install pre-commit==1.18.3
	pre-commit install
	pre-commit install-hooks

.PHONY: pre_commit_tests
pre_commit_tests: ## Run pre-commit tests
	pre-commit run --all-files

.PHONY: test
test: clean  ## Run python tests
	nosetests

.PHONY: coverage
coverage: clean  ## Run python tests with coverage
	nosetests --with-coverage

.PHONY: scan
scan: ./build/lambda.zip ## Run scan function locally
	scripts/run-scan-lambda $(TEST_BUCKET) $(TEST_KEY)

.PHONY: update
update: ./build/lambda.zip ## Run update function locally
	scripts/run-update-lambda
