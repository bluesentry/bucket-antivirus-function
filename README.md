# bucket-antivirus-function

[![CircleCI](https://circleci.com/gh/upsidetravel/bucket-antivirus-function.svg?style=svg)](https://circleci.com/gh/upsidetravel/bucket-antivirus-function)

Scan new objects added to any s3 bucket using AWS Lambda. [more details in this post](https://engineering.upside.com/s3-antivirus-scanning-with-lambda-and-clamav-7d33f9c5092e)

## Features

- Easy to install
- Send events from an unlimited number of S3 buckets
- Prevent reading of infected files using S3 bucket policies
- Accesses the end-user’s separate installation of
open source antivirus engine [ClamAV](http://www.clamav.net/)

## How Does It Work?

![](../master/images/bucket-antivirus-function.png)

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
- Scan results are published to a SNS topic (optional)
- Files found to be INFECTED are automatically deleted (optional)

## Installation

### Build from Source

To build the archive to upload to AWS Lambda, run `make`.  The build process is completed using
the [amazonlinux](https://hub.docker.com/_/amazonlinux/) [Docker](https://www.docker.com)
 image.  The resulting archive will be built at `build/lambda.zip`.  This file will be
 uploaded to AWS for both Lambda functions below.

### AV Definition Bucket

Create an s3 bucket to store current antivirus definitions.  This
provides the fastest download speeds for the scanner.  This bucket can
be kept as private.  

To allow public access, useful for other accounts,
add the following policy to the bucket.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowPublic",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject",
                "s3:GetObjectTagging"
            ],
            "Resource": "arn:aws:s3:::<bucket-name>/*"
        }
    ]
}
```

### Definition Update Lambda

This function accesses the user’s ClamAV instance to download
updated definitions using `freshclam`.  It is recommended to run
this every 3 hours to stay protected from the latest threats.

1. Create the archive using the method in the
 [Build from Source](#build-from-source) section.
2. From the AWS Lambda Dashboard, click **Create function**
3. Choose **Author from scratch** on the *Create function* page
4. Name your function `bucket-antivirus-update` when prompted on the
*Configure function* step.
5. Set *Runtime* to `Python 2.7`
6.  Create a new role name `bucket-antivirus-update` that uses the
following policy document
```json
{
   "Version":"2012-10-17",
   "Statement":[
      {
         "Effect":"Allow",
         "Action":[
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
         ],
         "Resource":"*"
      },
      {
         "Action":[
            "s3:GetObject",
            "s3:GetObjectTagging",
            "s3:PutObject",
            "s3:PutObjectTagging",
            "s3:PutObjectVersionTagging"
         ],
         "Effect":"Allow",
         "Resource":"arn:aws:s3:::<bucket-name>/*"
      }
   ]
}
```
7. Click next to go to the Configuration page
8. Add a trigger from the left of **CloudWatch Event** using `rate(3 hours)`
for the **Schedule expression**.  Be sure to check **Enable trigger**
9. Choose **Upload a ZIP file** for *Code entry type* and select the archive
downloaded in step 1.
10. Add a single environment variable named `AV_DEFINITION_S3_BUCKET`
and set its value to the name of the bucket created to store your AV
definitions.
11. Set *Lambda handler* to `update.lambda_handler`
12. Under *Basic Settings*, set *Timeout* to **5 minutes** and *Memory* to
**512**
13. Save and test your function.  If prompted for test data, just use
the default provided.

### AV Scanner Lambda

1. Create the archive using the method in the
 [Build from Source](#build-from-source) section.
2. From the AWS Lambda Dashboard, click **Create function**
3. Choose **Author from scratch** on the *Create function* page
4. Name your function `bucket-antivirus-function`
5. Set *Runtime* to `Python 2.7`
6.  Create a new role name `bucket-antivirus-function` that uses the
following policy document
```json
{
   "Version":"2012-10-17",
   "Statement":[
      {
         "Effect":"Allow",
         "Action":[
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
         ],
         "Resource":"*"
      },
      {
         "Action":[
            "s3:*"
         ],
         "Effect":"Allow",
         "Resource":"*"
      }
   ]
}
```
7. Click *next* to head to the Configuration page
8. Add a new trigger of type **S3 Event** using `ObjectCreate(all)`.
9. Choose **Upload a ZIP file** for *Code entry type* and select the archive
created in step 1.
10. Set *Lambda handler* to `scan.lambda_handler`
11. Add a single environment variable named `AV_DEFINITION_S3_BUCKET`
and set its value to the name of the bucket created to store your AV
definitions. If your bucket is `s3://my-bucket`, the value should be `my-bucket`.
12. Under *Basic settings*, set *Timeout* to **5 minutes** and *Memory* to
**1024**
13. Save the function.  Testing is easiest performed by uploading a
file to the bucket configured as the trigger in step 4.

### S3 Events

Configure scanning of additional buckets by adding a new S3 event to
invoke the Lambda function.  This is done from the properties of any
bucket in the AWS console.

![](../master/images/s3-event.png)

Note: If configured to update object metadata, events must only be
configured for `PUT` and `POST`. Metadata is immutable, which requires
the function to copy the object over itself with updated metadata. This
can cause a continuous loop of scanning if improperly configured.


## Configuration

Runtime configuration is accomplished using environment variables.  See
the table below for reference.

| Variable | Description | Default | Required |
| --- | --- | --- | --- |
| AV_DEFINITION_S3_BUCKET | Bucket containing antivirus definition files |  | Yes |
| AV_DEFINITION_S3_PREFIX | Prefix for antivirus definition files | clamav_defs | No |
| AV_DEFINITION_PATH | Path containing files at runtime | /tmp/clamav_defs | No |
| AV_SCAN_START_SNS_ARN | SNS topic ARN to publish notification about start of scan | | No |
| AV_SCAN_START_METADATA | The tag/metadata indicating the start of the scan | av-scan-start | No |
| AV_STATUS_CLEAN | The value assigned to clean items inside of tags/metadata | CLEAN | No |
| AV_STATUS_INFECTED | The value assigned to clean items inside of tags/metadata | INFECTED | No |
| AV_STATUS_METADATA | The tag/metadata name representing file's AV status | av-status | No |
| AV_STATUS_SNS_ARN | SNS topic ARN to publish scan results (optional) | | No |
| AV_TIMESTAMP_METADATA | The tag/metadata name representing file's scan time | av-timestamp | No |
| CLAMAVLIB_PATH | Path to ClamAV library files | ./bin | No |
| CLAMSCAN_PATH | Path to ClamAV clamscan binary | ./bin/clamscan | No |
| FRESHCLAM_PATH | Path to ClamAV freshclam binary | ./bin/freshclam | No |
| DATADOG_API_KEY | API Key for pushing metrics to DataDog (optional) | | No |
| AV_PROCESS_ORIGINAL_VERSION_ONLY | Controls that only original version of an S3 key is processed (if bucket versioning is enabled) | False | No |
| AV_DELETE_INFECTED_FILES | Controls whether infected files should be automatically deleted | False | No |

## S3 Bucket Policy Examples

### Deny to download the object if not "CLEAN"
This policy doesn't allow to download the object until:
1) The lambda that run Clam-AV is finished (so the object has a tag)
2) The file is not CLEAN

Please make sure to check cloudtrail for the arn:aws:sts, just find the event open it and copy the sts.       
It should be in the format provided below:
```
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
```
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

## License

```
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
