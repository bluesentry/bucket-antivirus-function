AWS_ACCESS_KEY_ID  ?= XXXXX
AWS_SECRET_ACCESS_KEY ?= YYYY
AWS_DEFAULT_REGION ?= us-east-1
ENVIRONMENT ?= staging

current_dir := $(shell pwd)
container_dir := /opt/app

archive:
	make -C ../../ archive
init:
	docker run --rm -ti \
		-v $(current_dir):$(container_dir) \
		-e ENVIRONMENT=$(ENVIRONMENT) \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)\
		-e AWS_DEFAULT_REGION=$(AWS_DEFAULT_REGION) \
		--workdir=$(container_dir)\
		hashicorp/terraform:0.11.1 \
	        init
plan: init archive
	docker run --rm -ti \
		-v $(current_dir):$(container_dir) \
		-e ENVIRONMENT=$(ENVIRONMENT) \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)\
		-e AWS_DEFAULT_REGION=$(AWS_DEFAULT_REGION) \
		--workdir=$(container_dir)\
		hashicorp/terraform:0.11.1 \
	        plan -var environment=$(ENVIRONMENT)
apply: init archive
	docker run --rm -ti \
		-v $(current_dir):$(container_dir) \
		-e ENVIRONMENT=$(ENVIRONMENT) \
		-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
		-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)\
		-e AWS_DEFAULT_REGION=$(AWS_DEFAULT_REGION) \
		--workdir=$(container_dir)\
		hashicorp/terraform:0.11.1 \
	        apply -var environment=$(ENVIRONMENT)
clean:
	rm -rf $(current_dir)/.terraform
	make -C ../../ clean
