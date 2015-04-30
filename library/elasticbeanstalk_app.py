#!/usr/bin/python

DOCUMENTATION = '''
---
module: elasticbeanstalk_app
short_description: create, update, delete and list beanstalk application
description:
    - creates, updates, deletes beanstalk applications if app_name is provided. Can also list applications

options:
  app_name:
    description:
      - name of the beanstalk application you wish to manage
    required: true
    default: null
  description:
    description:
      - describes the application
    required: false
    default: null
  state:
    description:
      - whether to ensure the application is present or absent, or to list existing applications
    required: false
    default: present
    choices: ['absent','present','list']
author: Harpreet Singh
extends_documentation_fragment: aws
'''

EXAMPLES = '''
# Create or update an application
- elasticbeanstalk_app:
    app_name: Sample App
    description: Hello World App
    region: us-east-1

# Delete application
- elasticbeanstalk_app:
    app_name: Sample App
    state: absent
    region: us-west-2

# List application applications
- elasticbeanstalk_app:
    state: list
    region: us-west-1
'''

try:
    import boto.beanstalk
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


def describe_app(ebs, app_name):
    apps = list_apps(ebs, app_name)

    return None if len(apps) != 1 else apps[0]

def list_apps(ebs, app_name):
    apps = ebs.describe_applications(app_name)
    apps = apps["DescribeApplicationsResponse"]["DescribeApplicationsResult"]["Applications"]

    return apps

def check_app(ebs, app, module):
    app_name = module.params['app_name']
    description = module.params['description']
    state = module.params['state']

    result = {}

    if state == 'present' and app is None:
        result = dict(changed=True, output = "App would be created")
    elif state == 'present' and app["Description"] != description:
        result = dict(changed=True, output = "App would be updated", app=app)
    elif state == 'present' and app["Description"] == description:
        result = dict(changed=False, output="App is up-to-date", app=app)
    elif state == 'absent' and app is None:
        result = dict(changed=False, output="App does not exist")
    elif state == 'absent' and app is not None:
        result = dict(changed=True, output="App will be deleted", app=app)

    module.exit_json(**result)

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
            app_name       = dict(),
            description    = dict(),
            state          = dict(choices=['present','absent','list'], default='present')
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_BOTO:
        module.fail_json(msg='boto required for this module')

    app_name = module.params['app_name']
    description = module.params['description']
    state = module.params['state']

    if app_name is None:
        if state != 'list':
            module.fail_json('Module parameter "app_name" is required if "state" is not "list"')

    result = {}
    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module)

    try:
        ebs = boto.beanstalk.connect_to_region(region)

    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg='No Authentication Handler found: %s ' % str(e))
    except Exception, e:
        module.fail_json(msg='Failed to connect to Beanstalk: %s' % str(e))


    app = describe_app(ebs, app_name)

    if module.check_mode and state != 'list':
        check_app(ebs, app, module)
        module.fail_json('ASSERTION FAILURE: check_app() should not return control.')

    if state == 'present':
        if app is None:
            create_app = ebs.create_application(app_name, description)
            app = describe_app(ebs, app_name)

            result = dict(changed=True, app=app)
        else:
            if app["Description"] != description:
                ebs.update_application(app_name, description)
                app = describe_app(ebs, app_name)

                result = dict(changed=True, app=app)
            else:
                result = dict(changed=False, app=app)

    elif state == 'absent':
        if app is None:
            result = dict(changed=False, output='Application not found')
        else:
            ebs.delete_application(app_name)
            result = dict(changed=True, app=app)

    else:
        apps = list_apps(ebs, app_name)
        result = dict(changed=False, apps=apps)

    module.exit_json(**result)


# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
