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

import boto3
import clamav
import copy
import json
import metrics
from common import *
from datetime import datetime
from distutils.util import strtobool

ENV = os.getenv("ENV", "")


def event_object(event, s3_resource=None):
    bucket = json.loads(event['Records'][0]['Sns']['Message'])['Records'][0]['s3']['bucket']['name']
    key = json.loads(event['Records'][0]['Sns']['Message'])['Records'][0]['s3']['object']['key']
    if (not bucket) or (not key):
        print("Unable to retrieve object from event.\n%s" % event)
        raise Exception("Unable to retrieve object from event.")
    if not s3_resource:
        return s3.Object(bucket, key)
    else:
        return s3_resource.Object(bucket, key)


def verify_s3_object_version(s3_object):
    # validate that we only process the original version of a file, if asked to do so
    # security check to disallow processing of a new (possibly infected) object version
    # while a clean initial version is getting processed
    # downstream services may consume latest version by mistake and get the infected version instead
    if str_to_bool(AV_PROCESS_ORIGINAL_VERSION_ONLY):
        bucketVersioning = s3.BucketVersioning(s3_object.bucket_name)
        if (bucketVersioning.status == "Enabled"):
            bucket = s3.Bucket(s3_object.bucket_name)
            versions = list(bucket.object_versions.filter(Prefix=s3_object.key))
            if len(versions) > 1:
                print("Detected multiple object versions in %s.%s, aborting processing" % (s3_object.bucket_name, s3_object.key))
                raise Exception("Detected multiple object versions in %s.%s, aborting processing" % (s3_object.bucket_name, s3_object.key))
            else:
                print("Detected only 1 object version in %s.%s, proceeding with processing" % (s3_object.bucket_name, s3_object.key))
        else:
            # misconfigured bucket, left with no or suspended versioning
            print("Unable to implement check for original version, as versioning is not enabled in bucket %s" % s3_object.bucket_name)
            raise Exception("Object versioning is not enabled in bucket %s" % s3_object.bucket_name)


def download_s3_object(s3_object, local_prefix):
    local_path = "%s/%s/%s" % (local_prefix, s3_object.bucket_name, s3_object.key)
    create_dir(os.path.dirname(local_path))
    s3_object.download_file(local_path)
    return local_path


def delete_s3_object(s3_object):
    try:
        s3_object.delete()
    except:
        print("Failed to delete infected file: %s.%s" % (s3_object.bucket_name, s3_object.key))
    else:
        print("Infected file deleted: %s.%s" % (s3_object.bucket_name, s3_object.key))


def set_av_tags(client, s3_object, result):
    curr_tags = client.get_object_tagging(Bucket=s3_object.bucket_name, Key=s3_object.key)["TagSet"]
    new_tags = copy.copy(curr_tags)
    for tag in curr_tags:
        if tag["Key"] in [AV_STATUS_METADATA, AV_TIMESTAMP_METADATA]:
            new_tags.remove(tag)
    new_tags.append({"Key": AV_STATUS_METADATA, "Value": result})
    new_tags.append({"Key": AV_TIMESTAMP_METADATA, "Value": datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC")})
    client.put_object_tagging(
        Bucket=s3_object.bucket_name,
        Key=s3_object.key,
        Tagging={"TagSet": new_tags}
    )


def sns_start_scan(s3_object):
    if AV_SCAN_START_SNS_ARN is None:
        return
    message = {
        "bucket": s3_object.bucket_name,
        "key": s3_object.key,
        "version": s3_object.version_id,
        AV_SCAN_START_METADATA: True,
        AV_TIMESTAMP_METADATA: datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC")
    }
    sns_client = boto3.client("sns")
    sns_client.publish(
        TargetArn=AV_SCAN_START_SNS_ARN,
        Message=json.dumps({'default': json.dumps(message)}),
        MessageStructure="json"
    )


def sns_scan_results(s3_object, result):
    if AV_STATUS_SNS_ARN is None:
        return
    message = {
        "bucket": s3_object.bucket_name,
        "key": s3_object.key,
        "version": s3_object.version_id,
        AV_STATUS_METADATA: result,
        AV_TIMESTAMP_METADATA: datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC")
    }
    sns_client = boto3.client("sns")
    sns_client.publish(
        TargetArn=AV_STATUS_SNS_ARN,
        Message=json.dumps({'default': json.dumps(message)}),
        MessageStructure="json",
        MessageAttributes={
            AV_STATUS_METADATA: {
                'DataType': 'String',
                'StringValue': result
            }
        }
    )


def sns_delete_results(s3_object, result):
    if AV_DELETE_INFECTED_FILES and AV_DELETE_SNS_ARN:
        message = {
            "ClamAV automation has detected an infected file was uploaded and deleted it.": {
                "bucket": s3_object.bucket_name,
                "key": s3_object.key,
                "version": s3_object.version_id,
                AV_STATUS_METADATA: result,
                AV_TIMESTAMP_METADATA: datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC")
            }
        }
        sns_client = boto3.client("sns")
        sns_client.publish(
            TargetArn=AV_DELETE_SNS_ARN,
            Message=json.dumps({'default': json.dumps(message)}),
            MessageStructure="json",
            MessageAttributes={
                AV_STATUS_METADATA: {
                    'DataType': 'String',
                    'StringValue': result
                }
            }
        )


def lambda_handler(event, context):
    if AV_SCAN_ROLE_ARN:
        sts_client = boto3.client('sts')
        sts_response = sts_client.assume_role(
            RoleArn=AV_SCAN_ROLE_ARN,
            RoleSessionName="AVScanRoleAssumption"
        )
        session = boto3.session.Session(
            aws_access_key_id=sts_response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=sts_response["Credentials"]["SecretAccessKey"],
            aws_session_token=sts_response["Credentials"]["SessionToken"]
        )
        s3_assumed = session.resource('s3')
        s3_current_client = session.client('s3')

    else:
        s3_assumed = None
        s3_current_client = s3_client

    start_time = datetime.utcnow()
    print("Script starting at %s\n" %
          (start_time.strftime("%Y/%m/%d %H:%M:%S UTC")))
    print("Event received: %s" % event)
    s3_object = event_object(event, s3_resource=s3_assumed)
    verify_s3_object_version(s3_object)
    sns_start_scan(s3_object)
    file_path = download_s3_object(s3_object, "/tmp")
    clamav.update_defs_from_s3(AV_DEFINITION_S3_BUCKET, AV_DEFINITION_S3_PREFIX)
    scan_result = clamav.scan_file(file_path)
    print("Scan of s3://%s resulted in %s\n" % (os.path.join(s3_object.bucket_name, s3_object.key), scan_result))
    set_av_tags(s3_current_client, s3_object, scan_result)
    sns_scan_results(s3_object, scan_result)
    metrics.send(env=ENV, bucket=s3_object.bucket_name, key=s3_object.key, status=scan_result)
    # Delete downloaded file to free up room on re-usable lambda function container
    try:
        os.remove(file_path)
    except OSError:
        pass
    if AV_DELETE_INFECTED_FILES and scan_result == AV_STATUS_INFECTED:
        sns_delete_results(s3_object, scan_result)
        delete_s3_object(s3_object)

    print("Script finished at %s\n" %
          datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC"))


def str_to_bool(s):
    return bool(strtobool(str(s)))
