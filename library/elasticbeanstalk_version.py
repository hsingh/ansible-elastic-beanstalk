#!/usr/bin/python

from ansible_collections.amazon.aws.plugins.module_utils.core import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.ec2 import boto3_conn, get_aws_connection_info

DOCUMENTATION = '''
---
module: elasticbeanstalk_version
short_description: create, update, delete and list beanstalk application versions
description:
  - creates, updates, deletes beanstalk versions if both app_name and version_label are provided.
  - Can also list versions associated with application
options:
  app_name:
    description:
      - name of the beanstalk application you wish to manage the versions of
    required: true
    default: null
  version_label:
    description:
      - label of the version you want create, update or delete
    required: false
    default: null
  s3_bucket:
    description:
      - name of the S3 bucket which contains the version source bundle
    required: false
    default: null
  s3_key:
    description:
      - S3 key where the source bundle is located.
      - Both s3_bucket and s3_key must be specified in order to create a new version.
    required: false
    default: null
  description:
    description:
      - describes the version
    required: false
    default: null
  delete_source:
    description:
      - Set to true to delete the source bundle from your storage bucket.
    required: false
    default: False
  state:
    description:
      - whether to ensure the version is present or absent, or to list existing versions
    required: false
    default: present
    choices: ['absent','present','list']
author: Harpreet Singh
extends_documentation_fragment: aws
'''

EXAMPLES = '''
# Create or update an application version
- elasticbeanstalk_version:
    app_name: Sample App
    version_label: v1.0.0
    description: Initial Version
    s3_bucket: sampleapp-versions-us-east-1
    s3_key: sample-app-1.0.0.zip
    region: us-east-1

# Delete application version
- elasticbeanstalk_version:
    app_name: Sample App
    version_label: v1.0.0
    state: absent
    region: us-west-2

# List application versions
- elasticbeanstalk_version:
    app_name: Sample App
    state: list
    region: us-west-1
'''

RETURN = '''
version:
    description: beanstalk application version
    returned: success and when state != list
    type: dict
    sample: {
        "ApplicationName": "app-name",
        "DateCreated": "2016-12-28T16:04:50.344000+00:00",
        "DateUpdated": "2016-12-28T16:05:58.593000+00:00",
        "Description": "version 1.0.0",
        "SourceBundle": {
            "S3Bucket": "s3-bucket",
            "S3Key": "s3/key/file-1.0.0.zip"
        },
        "Status": "UNPROCESSED",
        "VersionLabel": "1.0.0"
    }
versions:
    description: list of beanstalk application versions
    returned: when state == list
    type: list
    sample: [
        {
            "ApplicationName": "app-name",
            "DateCreated": "2016-12-28T16:04:50.344000+00:00",
            "DateUpdated": "2016-12-28T16:05:58.593000+00:00",
            "Description": "version 1.0.0",
            "SourceBundle": {
                "S3Bucket": "s3-bucket",
                "S3Key": "s3/key/file-1.0.0.zip"
            },
            "Status": "UNPROCESSED",
            "VersionLabel": "1.0.0"
        },
        {
            "ApplicationName": "app-name",
            "DateCreated": "2016-12-28T16:04:50.344000+00:00",
            "DateUpdated": "2016-12-28T16:05:58.593000+00:00",
            "Description": "version 1.0.1",
            "SourceBundle": {
                "S3Bucket": "s3-bucket",
                "S3Key": "s3/key/file-1.0.1.zip"
            },
            "Status": "UNPROCESSED",
            "VersionLabel": "1.0.1"
        }
    ]
output:
    description: message indicating what change will occur
    returned: in check mode
    type: string
    sample: Version is up-to-date
'''


class ApplicationVersionNotFound(Exception):
    def __init__(self, version_label):
        self.message = f"Application version with label: {version_label} not found"


class MoreThanOneApplicationVersionFound(Exception):
    def __init__(self, version_label):
        self.message = f"More than one application version returned using the term {version_label}," \
                       f" please use a specific term."


def describe_version(aws_eb, app_name, version_label):
    version = aws_eb.describe_application_versions(ApplicationName=app_name, VersionLabels=[version_label])
    if len(version["ApplicationVersions"]) == 0:
        raise ApplicationVersionNotFound(version_label)
    elif len(version["ApplicationVersions"]) > 1:
        raise MoreThanOneApplicationVersionFound(version_label)
    else:
        return version["ApplicationVersions"][0]


def list_versions(aws_eb, app_name):
    versions = aws_eb.describe_application_versions(ApplicationName=app_name)
    return versions["ApplicationVersions"]


def check_version(version, module):
    description = module.params['description']
    state = module.params['state']

    result = {}

    if state == 'present' and version is None:
        result = dict(changed=True, output="Version would be created")
    elif state == 'present' and version.get("Description", None) != description:
        result = dict(changed=True, output="Version would be updated", version=version)
    elif state == 'present' and version.get("Description", None) == description:
        result = dict(changed=False, output="Version is up-to-date", version=version)
    elif state == 'absent' and version is None:
        result = dict(changed=False, output="Version does not exist")
    elif state == 'absent' and version is not None:
        result = dict(changed=True, output="Version will be deleted", version=version)

    module.exit_json(**result)


def filter_empty(**kwargs):
    result = {}
    for key, value in kwargs.items():
        if value is not None:
            result.update({key: value})
    return result


def main():
    argument_spec = dict(
        app_name=dict(type='str', required=True),
        version_label=dict(type='str', required=False),
        s3_bucket=dict(type='str', required=False),
        s3_key=dict(type='str', required=False),
        description=dict(type='str', required=False),
        delete_source=dict(type='bool', default=False),
        state=dict(choices=['present', 'absent', 'list'], default='present')
    )

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)

    app_name = module.params['app_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']
    delete_source = module.params['delete_source']
    s3_bucket = module.params['s3_bucket']
    s3_key = module.params['s3_key']

    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)

    if not region:
        module.fail_json(msg='region must be specified')

    if app_name is None or app_name == '':
        module.fail_json(msg='app_name is required')

    aws_eb = boto3_conn(module, conn_type='client', resource='elasticbeanstalk',
                        region=region, endpoint=ec2_url, **aws_connect_params)

    if version_label is None and state != 'list':
        module.fail_json(msg='Module parameter "version_label" is required if "state" is not "list"')

    if s3_bucket is None and s3_key is None and state == 'present':
        module.fail_json(msg='Module parameter "s3_bucket" and "s3_key" is required if "state" is "present"')

    if state != 'list':
        try:
            version = describe_version(aws_eb, app_name, version_label)
        except ApplicationVersionNotFound:
            version = None
        except MoreThanOneApplicationVersionFound as error:
            module.fail_json(msg=error.message)
    else:
        version = list_versions(aws_eb, app_name)

    if module.check_mode and state != 'list':
        check_version(version, module)
        module.fail_json(msg='ASSERTION FAILURE: check_version() should not return control.')

    if state == 'present':
        if version is None:
            aws_eb.create_application_version(**filter_empty(ApplicationName=app_name,
                                                             VersionLabel=version_label,
                                                             Description=description,
                                                             SourceBundle={'S3Bucket': s3_bucket,
                                                                           'S3Key': s3_key}))
            version = describe_version(aws_eb, app_name, version_label)

            result = dict(changed=True, version=version)
        else:
            if version.get("Description", None) != description:
                aws_eb.update_application_version(ApplicationName=app_name,
                                                  VersionLabel=version_label,
                                                  Description='' if description is None else description)
                version = describe_version(aws_eb, app_name, version_label)

                result = dict(changed=True, version=version)
            else:
                result = dict(changed=False, version=version)

    elif state == 'absent':
        if version is None:
            result = dict(changed=False, output='Version not found')
        else:
            aws_eb.delete_application_version(ApplicationName=app_name,
                                              VersionLabel=version_label,
                                              DeleteSourceBundle=delete_source)
            result = dict(changed=True, version=version)

    else:
        result = dict(changed=False, versions=version)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
