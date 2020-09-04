#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ec2 import boto3_conn, ec2_argument_spec, get_aws_connection_info
try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

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
    required: false
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

RETURN = '''
app:
    description: beanstalk application
    returned: success and when state != list
    type: dict
    sample: {
        "ApplicationName": "app-name",
        "ConfigurationTemplates": [],
        "DateCreated": "2016-12-28T14:50:03.185000+00:00",
        "DateUpdated": "2016-12-28T14:50:03.185000+00:00",
        "Description": "description",
        "Versions": [
            "1.0.0",
            "1.0.1"
        ]
    }
apps:
    description: list of beanstalk applications
    returned: when state == list
    type: list
    sample: [
        {
            "ApplicationName": "app1",
            "ConfigurationTemplates": [],
            "DateCreated": "2016-12-28T14:50:03.185000+00:00",
            "DateUpdated": "2016-12-28T14:50:03.185000+00:00",
            "Description": "description"
        },
        {
            "ApplicationName": "app2",
            "ConfigurationTemplates": [],
            "DateCreated": "2016-12-28T14:50:03.185000+00:00",
            "DateUpdated": "2016-12-28T14:50:03.185000+00:00",
            "Description": "description"
        }
    ]
output:
    description: message indicating what change will occur
    returned: in check mode
    type: string
    sample: App is up-to-date
'''


def describe_app(ebs, app_name):
    apps = list_apps(ebs, app_name)
    return None if len(apps) != 1 else apps[0]


def list_apps(ebs, app_name):
    if app_name is not None:
        apps = ebs.describe_applications(ApplicationNames=[app_name])
    else:
        apps = ebs.describe_applications()
    return apps.get("Applications", [])


def check_app(app, module):
    description = module.params['description']
    state = module.params['state']
    result = {}
    if state == 'present' and app is None:
        result = dict(changed=True, output="App would be created")
    elif state == 'present' and app.get("Description", None) != description:
        result = dict(changed=True, output="App would be updated", app=app)
    elif state == 'present' and app.get("Description", None) == description:
        result = dict(changed=False, output="App is up-to-date", app=app)
    elif state == 'absent' and app is None:
        result = dict(changed=False, output="App does not exist")
    elif state == 'absent' and app is not None:
        result = dict(changed=True, output="App will be deleted", app=app)
    module.exit_json(**result)


def filter_empty(**kwargs):
    return {key: value for key, value in kwargs.items() if value}


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        app_name=dict(type='str', required=False),
        description=dict(type='str', required=False),
        state=dict(choices=['present', 'absent', 'list'], default='present')
    ),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)
    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')
    app_name = module.params['app_name']
    description = module.params['description']
    state = module.params['state']
    if app_name is None:
        if state != 'list':
            module.fail_json(msg='Module parameter "app_name" is required if "state" is not "list"')
    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)
    if region is None:
        module.fail_json(msg='region must be specified')
    ebs = boto3_conn(module, conn_type='client', resource='elasticbeanstalk',
                     region=region, endpoint=ec2_url, **aws_connect_params)

    app = describe_app(ebs, app_name)
    if module.check_mode and state != 'list':
        check_app(app, module)
        module.fail_json(msg='ASSERTION FAILURE: check_app() should not return control.')
    if state == 'present':
        if app is None:
            ebs.create_application(**filter_empty(ApplicationName=app_name, Description=description))
            app = describe_app(ebs, app_name)
            result = dict(changed=True, app=app)
        else:
            if app.get("Description", None) != description:
                ebs.update_application(ApplicationName=app_name,
                                       Description=description)
                app = describe_app(ebs, app_name)
                result = dict(changed=True, app=app)
            else:
                result = dict(changed=False, app=app)
    elif state == 'absent':
        if app is None:
            result = dict(changed=False, output='Application not found')
        else:
            ebs.delete_application(ApplicationName=app_name)
            result = dict(changed=True, app=app)
    else:
        apps = list_apps(ebs, app_name)
        result = dict(changed=False, apps=apps)
    module.exit_json(**result)


if __name__ == '__main__':
    main()
