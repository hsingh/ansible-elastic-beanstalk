#!/usr/bin/python

DOCUMENTATION = '''
---
module: elasticbeanstalk_configurationtemplate
short_description: create, update, delete and list beanstalk application versions
description:
    - creates, updates, deletes beanstalk configuration templates. Can also list versions associated with application
options:
  app_name:
    description:
      - name of the configuration template you wish to manage
    required: true
    default: null
  description:
    description:
      - describes this configuration template
    required: false
    default: null
  template_name:
    description:
      - name of the configuration template
    required: false
    default: null
  solution_stack_name:
    description:
      - TODO
    required: false
    default: null
  option_settings:
    description:
      - 'A dictionary array of settings to add of the form: { Namespace: ..., OptionName: ... , Value: ... }. If specified, AWS Elastic Beanstalk sets the specified configuration options to the requested value in the configuration set for the new environment. These override the values obtained from the solution stack or the configuration template'
    required: false
    default: null
  tags:
    description:
      - A dictionary of Key/Value tags to apply to the configuration template on creation. Tags cannot be modified once the environment is created.
    required: false
    default: null
  state:
    description:
      - whether to ensure the configuration template is present or absent, or to list existing configuration templates
    required: false
    default: present
    choices: ['absent','present','list','details']

author: Reginald Eli Deinla
extends_documentation_fragment: aws
'''

EXAMPLES = '''
TODO
'''

RETURN = '''
TODO
'''


try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from elasticbeanstalk_configurationtemplate import new_or_changed_option

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ec2 import boto3_conn, ec2_argument_spec, get_aws_connection_info

def describe_configurationtemplate(ebs, app_name, template_name):
    versions = list_versions(ebs, app_name, template_name)

    return None if len(versions) != 1 else versions[0]

def list_configurationtemplate(ebs, app_name, template_name):
    if template_name is None:
        settings = ebs.describe_configuration_settings(ApplicationName=app_name)
    else:
        settings = ebs.describe_configuration_settings(ApplicationName=app_name, TemplateName=template_name)

    return settings["ConfigurationSettings"]


def update_required(ebs, configurationtemplate, params):
    updates = []
    if params["solution_stack_name"] and configurationtemplate["SolutionStackName"] != params["solution_stack_name"]:
        updates.append(('SolutionStackName', configurationtemplate['SolutionStackName'], params['solution_stack_name']))

    if params["version_label"] and configurationtemplate["VersionLabel"] != params["version_label"]:
        updates.append(('VersionLabel', configurationtemplate['VersionLabel'], params['version_label']))

    if params["version_label"] and configurationtemplate["VersionLabel"] != params["version_label"]:
        updates.append(('VersionLabel', configurationtemplate['VersionLabel'], params['version_label']))

    for setting in params["option_settings"]:
        change = new_or_changed_option(options, setting)
        if change is not None:
            updates.append(change)

    return updates

def check_configurationtemplate(ebs, version, module):
    app_name = module.params['app_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']

    result = {}

    if state == 'present' and version is None:
        result = dict(changed=True, output = "Version would be created")
    elif state == 'present' and version.get("Description", None) != description:
        result = dict(changed=True, output = "Version would be updated", version=version)
    elif state == 'present' and version.get("Description", None) == description:
        result = dict(changed=False, output="Version is up-to-date", version=version)
    elif state == 'absent' and version is None:
        result = dict(changed=False, output="Version does not exist")
    elif state == 'absent' and version is not None:
        result = dict(changed=True, output="Version will be deleted", version=version)

    module.exit_json(**result)

def filter_empty(**kwargs):
    return {k:v for k,v in kwargs.iteritems() if v}

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
            app_name       = dict(type='str', required=True),
            template_name  = dict(type='str', required=False),
            description    = dict(type='str', required=False),
            state          = dict(choices=['present','absent','list','details'], default='present'),
            solution_stack_name = dict(type='str', required=False),
            option_settings = dict(type='list',default=[]),
            tags = dict(type='dict',default=dict()),
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    app_name = module.params['app_name']
    description = module.params['description']
    state = module.params['state']
    template_name = module.params['template_name']
    solution_stack_name = module.params['solution_stack_name']
    tags = module.params['tags']
    option_settings = module.params['option_settings']

    result = {}
    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)

    if region:
        ebs = boto3_conn(module, conn_type='client', resource='elasticbeanstalk',
                region=region, endpoint=ec2_url, **aws_connect_params)
    else:
        module.fail_json(msg='region must be specified')


    version = describe_version(ebs, app_name, version_label)

    if module.check_mode and state != 'list':
        check_version(ebs, version, module)
        module.fail_json(msg='ASSERTION FAILURE: check_version() should not return control.')

    if state == 'list':
        try:
            configurationtemplate = describe_configurationtemplate(ebs, app_name, template_name)
            result = dict(changed=False, configurationtemplate=[] if configurationtemplate is None else configurationtemplate)
        except ClientError, e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    if state == 'details':
        try:
            configurationtemplate = describe_configuration_template(ebs, app_name, template_name)
            result = dict(changed=False, configurationtemplate=configurationtemplate)
        except ClientError, e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    if module.check_mode and (state != 'list' or state != 'details'):
        check_env(ebs, app_name, env_name, module)
        module.fail_json('ASSERTION FAILURE: check_version() should not return control.')

    if state == 'present':
        try:
            tags_to_apply = [ {'Key':k,'Value':v} for k,v in tags.iteritems()]
            configurationtemplate = ebs.create_configuration_template(**filter_empty(ApplicationName=app_name,
                                                  VersionLabel=version_label,
                                                  TemplateName=template_name,
                                                  Tags=tags_to_apply,
                                                  SolutionStackName=solution_stack_name,
                                                  Description=description,
                                                  OptionSettings=option_settings))
            result = dict(changed=True, configurationtemplate=configurationtemplate)
        except ClientError, e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    if update:
        try:
            env = describe_configuration_template(ebs, app_name, template_name)
            updates = update_required(ebs, env, module.params)
            if len(updates) > 0:
                configurationtemplate = ebs.update_configuration_template(**filter_empty(
                                       ApplicationName=app_name,
                                       TemplateName=template_name,
                                       Description=description,
                                       OptionSettings=option_settings))
                result = dict(changed=True, configurationtemplate=configurationtemplate, updates=updates)
            else:
                result = dict(changed=False, configurationtemplate=configurationtemplate)
        except ClientError, e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    if state == 'absent':
        try:
            ebs.delete_configuration_template(EnvironmentName=env_name)
            result = dict(changed=True)
        except ClientError, e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    module.exit_json(**result)

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import boto3_conn, ec2_argument_spec, get_aws_connection_info, camel_dict_to_snake_dict

if __name__ == '__main__':
    main()
