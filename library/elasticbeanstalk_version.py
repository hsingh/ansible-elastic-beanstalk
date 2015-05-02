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
  days_to_store:
    description:
      - limit time (in days) of application versions to keep (for 'cleanup' state). If specified together with files_to_keep, more effective cleanup will take in place.
    required: false
    default: null
  files_to_store:
    description:
      - limit amount of application versions to keep (for 'cleanup' state). If specified together with days_to_store, more effective cleanup will take in place.
    required: false
    default: null
  delete_source:
    description:
      - indicates whether to delete the associated source bundle from Amazon S3. Valid Values: true | false
    required: false
    default: false
  state:
    description:
      - whether to ensure the version is present or absent, or to list existing versions, or to clean up old versions
    required: false
    default: present
    choices: ['absent','present','list','cleanup']
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

# Clean up old application versions
- elasticbeanstalk_version:
    app_name: Sample App
    state: cleanup
    region: us-west-1
    days_to_store: 7
    files_to_store: 15
'''

import time, operator

try:
    import boto.beanstalk, boto.exception
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

def list_versions_sorted(ebs, app_name, version_label):
    versions = sorted(list_versions(ebs, app_name, version_label), key=operator.itemgetter("DateCreated"), reverse=True)

    return versions if len(versions) > 0 else None

def remove_versions(ebs, app_name, list_to_remove, delete_source):
    for version in list_to_remove:
        try:
            ebs.delete_application_version(app_name, version['VersionLabel'], delete_source)
        except boto.exception.BotoServerError as error:
            # ignore if file on S3 doesn't exist
            if error.error_code == 'SourceBundleDeletionFailure':
                pass
            else:
                return False
        except:
            return False

    return True

def get_cleanup_versions_by_date(versions, deployed_versions, days_to_store):
    targetTime = time.time()-(86400*days_to_store)
    delete_list_days = []
    for version in versions:
        if version["DateUpdated"] < targetTime and version["VersionLabel"] not in deployed_versions:
            delete_list_days.append(version)
    return None if len(delete_list_days) == 0 else delete_list_days

def get_cleanup_versions_by_files(versions, deployed_versions, files_to_store):
    delete_list_count = []
    for index, version in enumerate(versions):
        if index > (files_to_store-1) and version["VersionLabel"] not in deployed_versions:
            delete_list_count.append(version)
    return None if len(delete_list_count) == 0 else delete_list_count

def get_deployed_versions_by_app(ebs, app_name):
    envs = ebs.describe_environments(app_name)
    envs = envs["DescribeEnvironmentsResponse"]["DescribeEnvironmentsResult"]["Environments"]

    deployed_versions = []
    for env in envs:
        deployed_versions.append(env['VersionLabel'])

    return deployed_versions

def get_cleanup_versions(ebs, app_name, versions, days_to_store, files_to_store):
    deployed_versions = get_deployed_versions_by_app(ebs, app_name)
    if days_to_store and files_to_store:
        delete_list_days = get_cleanup_versions_by_date(versions, deployed_versions, days_to_store)
        delete_list_count = get_cleanup_versions_by_files(versions, deployed_versions, files_to_store)

        if delete_list_count and delete_list_days:
            return delete_list_days if len(delete_list_count) < len(delete_list_days) else delete_list_count
        elif delete_list_days is None and delete_list_count is not None:
            return delete_list_count
        elif delete_list_count is None and delete_list_days is not None:
            return delete_list_days
        elif delete_list_count is None and delete_list_days is None:
            return None

    elif days_to_store and files_to_store is None:
        return get_cleanup_versions_by_date(versions, deployed_versions, days_to_store)

    elif files_to_store and days_to_store is None:
        return get_cleanup_versions_by_files(versions, deployed_versions, files_to_store)

def check_version(ebs, version, module):
    app_name = module.params['app_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']

    result = {}

    if state == 'present' and version is None:
        result = dict(changed=True, output ="Version would be created")
    elif state == 'present' and version["Description"] != description:
        result = dict(changed=True, output ="Version would be updated", version=version)
    elif state == 'present' and version["Description"] == description:
        result = dict(changed=False, output="Version is up-to-date", version=version)
    elif state == 'absent' and version is None:
        result = dict(changed=False, output="Version does not exist")
    elif state == 'absent' and version is not None:
        result = dict(changed=True, output="Version will be deleted", version=version)

    module.exit_json(**result)

def check_cleanup(ebs, app_name, versions, days_to_store, files_to_store, module):
    app_name = module.params['app_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']

    result = {}

    if versions is None:
        result = dict(changed=False, output='Versions not found for application')
    else:
        versions_to_delete = get_cleanup_versions(ebs, app_name, versions, days_to_store, files_to_store)
        if versions_to_delete is None:
            result = dict(changed=False, output="Nothing is going to be deleted")
        else:
            result = dict(changed=True, output="Following %s versions will be removed" % len(versions_to_delete), versions_to_delete=versions_to_delete)

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
            days_to_store  = dict(),
            files_to_store = dict(),
            state          = dict(choices=['present','absent','list','cleanup'], default='present')
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
    days_to_store = module.params['days_to_store']
    files_to_store = module.params['files_to_store']

    if version_label is None:
        if state not in ["list", "cleanup"]:
            module.fail_json(msg='Module parameter "version_label" is required if "state" is not "list"')

    if module.params['s3_bucket'] is None and module.params['s3_key'] is None:
        if state == 'present':
            module.fail_json(msg='Module parameter "s3_bucket" or "s3_key" is required if "state" is "present"')

    if module.params['days_to_store'] is None and module.params['files_to_store'] is None:
        if state == 'cleanup':
            module.fail_json(msg='Module parameters "days_to_store" and/or "files_to_store" are required if "state" is "cleanup"')

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


    if module.check_mode and state != 'list' and state != 'cleanup':
        version = describe_version(ebs, app_name, version_label)
        check_version(ebs, version, module)
        module.fail_json('ASSERTION FAILURE: check_version() should not return control.')
    elif module.check_mode and state == 'cleanup':
        versions = list_versions_sorted(ebs, app_name, version_label)
        check_cleanup(ebs, app_name, versions, days_to_store, files_to_store, module)
        module.fail_json('ASSERTION FAILURE: check_cleanup() should not return control.')


    if state == 'present':
        version = describe_version(ebs, app_name, version_label)
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
        version = describe_version(ebs, app_name, version_label)
        if version is None:
            result = dict(changed=False, output='Version not found for application: %s' % app_name)
        else:
            ebs.delete_application_version(app_name, version_label, delete_source)

            result = dict(changed=True, version=version)

    elif state == 'cleanup':
        versions = list_versions_sorted(ebs, app_name, version_label)
        if versions is None:
            result = dict(changed=False, output='Versions not found for application: %s' % app_name)
        else:
            versions_to_delete = get_cleanup_versions(ebs, app_name, versions, days_to_store, files_to_store)
            if versions_to_delete is None:
                result = dict(changed=False, output="Nothing to remove for given parameters")
            else:
                if remove_versions(ebs, app_name, versions_to_delete, delete_source):
                    result = dict(changed=True, output="Removed %s version(s) for given parameters" % len(versions_to_delete))
                else:
                    result = dict(changed=False, output="Unable to remove versions for application: %s" % app_name)

    else:
        versions = list_versions(ebs, app_name, version_label)

        result = dict(changed=False, versions=versions)

    module.exit_json(**result)


# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
