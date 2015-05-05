#!/usr/bin/python

DOCUMENTATION = '''
---
module: elasticbeanstalk_version
short_description: create, update, delete and list beanstalk application versions
description:
    - creates, updates, deletes beanstalk versions if both app_name and version_label are provided. Can also list versions associated with application
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
      - S3 key where the source bundle is located. Both s3_bucket and s3_key must be specified in order to create a new version.
    required: false
    default: null
  description:
    description:
      - describes the version
    required: false
    default: null
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

try:
    import boto.beanstalk
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def describe_version(ebs, app_name, version_label):
    versions = list_versions(ebs, app_name, version_label)

    return None if len(versions) != 1 else versions[0]

def list_versions(ebs, app_name, version_label):
    versions = ebs.describe_application_versions(app_name, version_label)
    versions = versions["DescribeApplicationVersionsResponse"]["DescribeApplicationVersionsResult"]["ApplicationVersions"]

    return versions

def check_version(ebs, version, module):
    app_name = module.params['app_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']

    result = {}

    if state == 'present' and version is None:
        result = dict(changed=True, output = "Version would be created")
    elif state == 'present' and version["Description"] != description:
        result = dict(changed=True, output = "Version would be updated", version=version)
    elif state == 'present' and version["Description"] == description:
        result = dict(changed=False, output="Version is up-to-date", version=version)
    elif state == 'absent' and version is None:
        result = dict(changed=False, output="Version does not exist")
    elif state == 'absent' and version is not None:
        result = dict(changed=True, output="Version will be deleted", version=version)

    module.exit_json(**result)

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
            app_name       = dict(required=True),
            version_label  = dict(),
            s3_bucket      = dict(),
            s3_key         = dict(),
            description    = dict(),
            delete_source  = dict(type='bool',default=False),
            state          = dict(choices=['present','absent','list'], default='present')
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_BOTO:
        module.fail_json(msg='boto required for this module')

    app_name = module.params['app_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']
    delete_source = module.params['delete_source']

    if version_label is None:
        if state != 'list':
            module.fail_json('Module parameter "version_label" is required if "state" is not "list"')

    if module.params['s3_bucket'] is None and module.params['s3_key'] is None:
        if state == 'present':
            module.fail_json('Module parameter "s3_bucket" or "s3_key" is required if "state" is "present"')

    if module.params['s3_bucket'] is not None:
        s3_bucket = module.params['s3_bucket']

    if module.params['s3_key'] is not None:
        s3_key = module.params['s3_key']


    result = {}
    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module)

    try:
        ebs = boto.beanstalk.connect_to_region(region)

    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg='No Authentication Handler found: %s ' % str(e))
    except Exception, e:
        module.fail_json(msg='Failed to connect to Beanstalk: %s' % str(e))


    version = describe_version(ebs, app_name, version_label)

    if module.check_mode and state != 'list':
        check_version(ebs, version, module)
        module.fail_json('ASSERTION FAILURE: check_version() should not return control.')


    if state == 'present':
        if version is None:
            create_req = ebs.create_application_version(app_name, version_label, description, s3_bucket, s3_key)
            version = describe_version(ebs, app_name, version_label)

            result = dict(changed=True, version=version)
        else:
            if version["Description"] != description:
                ebs.update_application_version(app_name, version_label, description)
                version = describe_version(ebs, app_name, version_label)

                result = dict(changed=True, version=version)
            else:
                result = dict(changed=False, version=version)

    elif state == 'absent':
        if version is None:
            result = dict(changed=False, output='Version not found')
        else:
            ebs.delete_application_version(app_name, version_label, delete_source)
            result = dict(changed=True, version=version)

    else:
        versions = list_versions(ebs, app_name, version_label)

        result = dict(changed=False, versions=versions)

    module.exit_json(**result)


# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
