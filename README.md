# bucket-antivirus-function

[![CircleCI](https://circleci.com/gh/upsidetravel/bucket-antivirus-function.svg?style=svg)](https://circleci.com/gh/upsidetravel/bucket-antivirus-function)

Scan new objects added to any s3 bucket using AWS Lambda. [more details in this post](https://engineering.upside.com/s3-antivirus-scanning-with-lambda-and-clamav-7d33f9c5092e)

## Features

- Easy to install
- Send events from an unlimited number of S3 buckets
- Prevent reading of infected files using S3 bucket policies
- Accesses the end-user’s separate installation of
open source antivirus engine [ClamAV](http://www.clamav.net/)

## How It Works

![architecture-diagram](../master/images/bucket-antivirus-function.png)

- Each time a new object is added to a bucket, S3 invokes the Lambda
function to scan the object
- The function package will download (if needed) current antivirus
definitions from a S3 bucket. Transfer speeds between a S3 bucket and
Lambda are typically faster and more reliable than another source
- The object is scanned for viruses and malware.  Archive files are
extracted and the files inside scanned also
- The objects tags are updated to reflect the result of the scan, CLEAN
or INFECTED, along with the date and time of the scan.
- Object metadata is updated to reflect the result of the scan (optional)
- Metrics are sent to [DataDog](https://www.datadoghq.com/) (optional)
- Scan results are published to a SNS topic (optional) (Optionally choose to only publish INFECTED results)
- Files found to be INFECTED are automatically deleted (optional)

## Installation

### Build from Source

To build the archive to upload to AWS Lambda, run `make all`.  The build process is completed using
the [amazonlinux](https://hub.docker.com/_/amazonlinux/) [Docker](https://www.docker.com)
 image.  The resulting archive will be built at `build/lambda.zip`.  This file will be
 uploaded to AWS for both Lambda functions below.

### Create Relevant AWS Infra via CloudFormation

Use CloudFormation with the `cloudformation.yaml` located in the `deploy/` directory to quickly spin up the AWS infra needed to run this project. CloudFormation will create:

- An S3 bucket that will store AntiVirus definitions.
- A Lambda Function called `avUpdateDefinitions` that will update the AV Definitions in the S3 Bucket every 3 hours.
This function accesses the user’s above S3 Bucket to download updated definitions using `freshclam`.
- A Lambda Function called `avScanner` that is triggered on each new S3 object creation which scans the object and tags it appropriately. It is created with `1600mb` of memory which should be enough, however if you start to see function timeouts, this memory may have to be bumped up. In the past, we recommended using `1024mb`, but that has started causing Lambda timeouts and bumping this memory has resolved it.

Running CloudFormation, it will ask for 2 inputs for this stack:

1. BucketType: `private` (default) or `public`. This is applied to the S3 bucket that stores the AntiVirus definitions. We recommend to only use `public` when other AWS accounts need access to this bucket.
2. SourceBucket: [a non-empty string]. The name (do not include `s3://`) of the S3 bucket that will have its objects scanned. _Note - this is just used to create the IAM Policy, you can add/change source buckets later via the IAM Policy that CloudFormation outputs_

After the Stack has successfully created, there are 3 manual processes that still have to be done:

1. Upload the `build/lambda.zip` file that was created by running `make all` to the `avUpdateDefinitions` and `avScanner` Lambda functions via the Lambda Console.
2. To trigger the Scanner function on new S3 objects, go to the `avScanner` Lambda function console, navigate to `Configuration` -> `Trigger` -> `Add Trigger` -> Search for S3, and choose your bucket(s) and select `All object create events`, then click `Add`. _Note - if you chose more than 1 bucket as the source, or chose a different bucket than the Source Bucket in the CloudFormation parameter, you will have to also edit the IAM Role to reflect these new buckets (see "Adding or Changing Source Buckets")_
3. Navigate to the `avUpdateDefinitions` Lambda function and manually trigger the function to get the initial Clam definitions in the bucket (instead of waiting for the 3 hour trigger to happen). Do this by clicking the `Test` section, and then clicking the orange `test` button. The function should take a few seconds to execute, and when finished you should see the `clam_defs` in the `av-definitions` S3 bucket.

#### Adding or Changing Source Buckets

Changing or adding Source Buckets is done by editing the `AVScannerLambdaRole` IAM Role. More specifically, the `S3AVScan` and `KmsDecrypt` parts of that IAM Role's policy.

### S3 Events

Configure scanning of additional buckets by adding a new S3 event to
invoke the Lambda function.  This is done from the properties of any
bucket in the AWS console.

![s3-event](../master/images/s3-event.png)

Note: If configured to update object metadata, events must only be
configured for `PUT` and `POST`. Metadata is immutable, which requires
the function to copy the object over itself with updated metadata. This
can cause a continuous loop of scanning if improperly configured.

## Configuration

Runtime configuration is accomplished using environment variables.  See
the table below for reference.

| Variable                         | Description                                                                                     | Default          | Required |
|----------------------------------|-------------------------------------------------------------------------------------------------|------------------|----------|
| AV_DEFINITION_S3_BUCKET          | Bucket containing antivirus definition files                                                    |                  | Yes      |
| AV_DEFINITION_S3_PREFIX          | Prefix for antivirus definition files                                                           | clamav_defs      | No       |
| AV_DEFINITION_PATH               | Path containing virus definition files at runtime                                               | /tmp/clamav_defs | No       |
| AV_SCAN_START_SNS_ARN            | SNS topic ARN to publish notification about start of scan                                       |                  | No       |
| AV_SCAN_START_METADATA           | The tag/metadata indicating the start of the scan                                               | av-scan-start    | No       |
| AV_SIGNATURE_METADATA            | The tag/metadata name representing file's AV type                                               | av-signature     | No       |
| AV_STATUS_CLEAN                  | The value assigned to clean items inside of tags/metadata                                       | CLEAN            | No       |
| AV_STATUS_INFECTED               | The value assigned to clean items inside of tags/metadata                                       | INFECTED         | No       |
| AV_STATUS_METADATA               | The tag/metadata name representing file's AV status                                             | av-status        | No       |
| AV_STATUS_SNS_ARN                | SNS topic ARN to publish scan results (optional)                                                |                  | No       |
| AV_STATUS_SNS_PUBLISH_CLEAN      | Publish AV_STATUS_CLEAN results to AV_STATUS_SNS_ARN                                            | True             | No       |
| AV_STATUS_SNS_PUBLISH_INFECTED   | Publish AV_STATUS_INFECTED results to AV_STATUS_SNS_ARN                                         | True             | No       |
| AV_TIMESTAMP_METADATA            | The tag/metadata name representing file's scan time                                             | av-timestamp     | No       |
| AV_EXTRA_VIRUS_DEFINITIONS       | Uses fangfrisch for extra antivirus definitions                                                 | False            | No       |
| CLAMAVLIB_PATH                   | Path to ClamAV library files                                                                    | ./bin            | No       |
| CLAMDSCAN_PATH                   | Path to ClamAV clamdscan binary                                                                 | ./bin/clamdscan  | No       |
| FRESHCLAM_PATH                   | Path to ClamAV freshclam binary                                                                 | ./bin/freshclam  | No       |
| DATADOG_API_KEY                  | API Key for pushing metrics to DataDog (optional)                                               |                  | No       |
| AV_PROCESS_ORIGINAL_VERSION_ONLY | Controls that only original version of an S3 key is processed (if bucket versioning is enabled) | False            | No       |
| AV_DELETE_INFECTED_FILES         | Controls whether infected files should be automatically deleted                                 | False            | No       |
| EVENT_SOURCE                     | The source of antivirus scan event "S3" or "SNS" (optional)                                     | S3               | No       |
| S3_ENDPOINT                      | The Endpoint to use when interacting wth S3                                                     | None             | No       |
| SNS_ENDPOINT                     | The Endpoint to use when interacting wth SNS                                                    | None             | No       |
| LAMBDA_ENDPOINT                  | The Endpoint to use when interacting wth Lambda                                                 | None             | No       |

## S3 Bucket Policy Examples

### Deny to download the object if not "CLEAN"

This policy doesn't allow to download the object until:

1. The lambda that run Clam-AV is finished (so the object has a tag)
2. The file is not CLEAN

Please make sure to check cloudtrail for the arn:aws:sts, just find the event open it and copy the sts.
It should be in the format provided below:

```json
 {
    "Effect": "Deny",
    "NotPrincipal": {
        "AWS": [
            "arn:aws:iam::<<aws-account-number>>:role/<<bucket-antivirus-role>>",
            "arn:aws:sts::<<aws-account-number>>:assumed-role/<<bucket-antivirus-role>>/<<bucket-antivirus-role>>",
            "arn:aws:iam::<<aws-account-number>>:root"
        ]
    },
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::<<bucket-name>>/*",
    "Condition": {
        "StringNotEquals": {
            "s3:ExistingObjectTag/av-status": "CLEAN"
        }
    }
}
```

### Deny to download and re-tag "INFECTED" object

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Deny",
      "Action": ["s3:GetObject", "s3:PutObjectTagging"],
      "Principal": "*",
      "Resource": ["arn:aws:s3:::<<bucket-name>>/*"],
      "Condition": {
        "StringEquals": {
          "s3:ExistingObjectTag/av-status": "INFECTED"
        }
      }
    }
  ]
}
```

## Manually Scanning Buckets

You may want to scan all the objects in a bucket that have not previously been scanned or were created
prior to setting up your lambda functions. To do this you can use the `scan_bucket.py` utility.

```sh
pip install boto3
scan_bucket.py --lambda-function-name=<lambda_function_name> --s3-bucket-name=<s3-bucket-to-scan>
```

This tool will scan all objects that have not been previously scanned in the bucket and invoke the lambda function
asynchronously. As such you'll have to go to your cloudwatch logs to see the scan results or failures. Additionally,
the script uses the same environment variables you'd use in your lambda so you can configure them similarly.

## Testing

There are two types of tests in this repository. The first is pre-commit tests and the second are python tests. All of
these tests are run by CircleCI.

### pre-commit Tests

The pre-commit tests ensure that code submitted to this repository meet the standards of the repository. To get started
with these tests run `make pre_commit_install`. This will install the pre-commit tool and then install it in this
repository. Then the github pre-commit hook will run these tests before you commit your code.

To run the tests manually run `make pre_commit_tests` or `pre-commit run -a`.

### Python Tests

The python tests in this repository use `unittest` and are run via the `nose` utility. To run them you will need
to install the developer resources and then run the tests:

```sh
pip install -r requirements.txt
pip install -r requirements-dev.txt
make test
```

### Local lambdas

You can run the lambdas locally to test out what they are doing without deploying to AWS. This is accomplished
by using docker containers that act similarly to lambda. You will need to have set up some local variables in your
`.envrc.local` file and modify them appropriately first before running `direnv allow`. If you do not have `direnv`
it can be installed with `brew install direnv`.

For the Scan lambda you will need a test file uploaded to S3 and the variables `TEST_BUCKET` and `TEST_KEY`
set in your `.envrc.local` file. Then you can run:

```sh
direnv allow
make archive scan
```

If you want a file that will be recognized as a virus you can download a test file from the [EICAR](https://www.eicar.org/?page_id=3950)
website and uploaded to your bucket.

For the Update lambda you can run:

```sh
direnv allow
make archive update
```

## License

```text
Upside Travel, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

ClamAV is released under the [GPL Version 2 License](https://github.com/vrtadmin/clamav-devel/blob/master/COPYING)
and all [source for ClamAV](https://github.com/vrtadmin/clamav-devel) is available
for download on Github.
