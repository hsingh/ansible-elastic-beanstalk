#!/usr/bin/python

DOCUMENTATION = '''
---
module: elasticbeanstalk_configuration_template
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
      - 'A dictionary array of settings to add of the form: { Namespace: ..., OptionName: ... , Value: ... }. If specified, AWS Elastic Beanstalk sets the specified configuration options to the requested value in the configuration set.'
    required: false
    default: null
  tags:
    description:
      - A dictionary of Key/Value tags to apply to the configuration template on creation. Tags cannot be modified once the configuration template is created.
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
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ec2 import boto3_conn, ec2_argument_spec, get_aws_connection_info


def describe_configuration_template(ebs, app_name, template_name, module):
    try:
        versions = list_configuration_template(ebs, app_name, template_name)
    except ClientError, e:
        if e.message.endswith("No Configuration Template named '{}/{}' found.".format(app_name, template_name)):
            versions = []
        else:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    return None if len(versions) != 1 else versions[0]

def list_configuration_template(ebs, app_name, template_name):
    if template_name is None:
        settings = ebs.describe_configuration_settings(ApplicationName=app_name)
    else:
        settings = ebs.describe_configuration_settings(ApplicationName=app_name, TemplateName=template_name)

    return settings["ConfigurationSettings"]

def new_or_changed_option(options, setting):
    for option in options:
        if option["Namespace"] == setting["Namespace"] and \
            option["OptionName"] == setting["OptionName"]:

            if (setting['Namespace'] in ['aws:autoscaling:launchconfiguration','aws:ec2:vpc'] and \
                setting['OptionName'] in ['SecurityGroups', 'ELBSubnets', 'Subnets'] and \
                set(setting['Value'].split(',')).issubset(setting['Value'].split(','))) or \
                option["Value"] == setting["Value"]:
                return None
            else:
                return (option["Namespace"] + ':' + option["OptionName"], option["Value"], setting["Value"])

    return (setting["Namespace"] + ':' + setting["OptionName"], "<NEW>", setting["Value"])

def update_required(ebs, configuration_template, params):
    updates = []
    if params["solution_stack_name"] and configuration_template["SolutionStackName"] != params["solution_stack_name"]:
        updates.append(('SolutionStackName', configuration_template['SolutionStackName'], params['solution_stack_name']))

    if params["description"] and configuration_template["Description"] != params["description"]:
        updates.append(('Description', configuration_template['Description'], params['description']))

    for setting in params["option_settings"]:
        change = new_or_changed_option(configuration_template['OptionSettings'], setting)
        if change is not None:
            updates.append(change)

    return updates

def check_configuration_template(ebs, configuration_template, module):
    state = module.params['state']
    result = {}

    if state == 'present' and configuration_template is None:
        result = dict(changed=True, output = "Configuration Template would be created")
    elif state == 'present' and configuration_template is not None:
        updates = update_required(ebs, configuration_template, module.params)
        if len(updates) > 0:
            result = dict(changed=True, output = "Configuration Template would be updated", configuration_template=configuration_template, updates=updates)
        else:
            result = dict(changed=False, output="Configuration Template is up-to-date", configuration_template=configuration_template)
    elif state == 'absent' and configuration_template is None:
        result = dict(changed=False, output="Configuration Template does not exist")
    elif state == 'absent' and configuration_template is not None:
        result = dict(changed=True, output="Configuration Template will be deleted", configuration_template=configuration_template)

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

    update = False
    result = {}
    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)

    if region:
        ebs = boto3_conn(module, conn_type='client', resource='elasticbeanstalk',
                region=region, endpoint=ec2_url, **aws_connect_params)
    else:
        module.fail_json(msg='region must be specified')


    configuration_template = describe_configuration_template(ebs, app_name, template_name, module)

    if module.check_mode and state != 'list':
        check_configuration_template(ebs, configuration_template, module)
        module.fail_json(msg='ASSERTION FAILURE: check_configuration_template() should not return control.')

    if state == 'list':
        try:
            configuration_template = describe_configuration_template(ebs, app_name, template_name, module)
            result = dict(changed=False, configuration_template=[] if configuration_template is None else configuration_template)
        except ClientError, e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    if state == 'details':
        try:
            configuration_template = describe_configuration_template(ebs, app_name, template_name, module)
            result = dict(changed=False, configuration_template=configuration_template)
        except ClientError, e:
            module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    if module.check_mode and (state != 'list' or state != 'details'):
        check_configuration_template(ebs, configuration_template, module)
        module.fail_json('ASSERTION FAILURE: check_configuration_template() should not return control.')

    if state == 'present':
        try:
            tags_to_apply = [ {'Key':k,'Value':v} for k,v in tags.iteritems()]
            configuration_template = ebs.create_configuration_template(**filter_empty(ApplicationName=app_name,
                                                  TemplateName=template_name,
                                                  Tags=tags_to_apply,
                                                  SolutionStackName=solution_stack_name,
                                                  Description=description,
                                                  OptionSettings=option_settings))
            result = dict(changed=True, configuration_template=configuration_template)
        except ClientError, e:
            if e.message.endswith('Configuration Template {} already exists.'.format(template_name)):
                update = True
            else:
                module.fail_json(msg=e.message, **camel_dict_to_snake_dict(e.response))

    if update:
        try:
            configuration_template = describe_configuration_template(ebs, app_name, template_name, module)
            updates = update_required(ebs, configuration_template, module.params)
            if len(updates) > 0:
                configuration_template = ebs.update_configuration_template(**filter_empty(
                                       ApplicationName=app_name,
                                       TemplateName=template_name,
                                       Description=description,
                                       OptionSettings=option_settings))
                result = dict(changed=True, configuration_template=configuration_template, updates=updates)
            else:
                result = dict(changed=False, configuration_template=configuration_template)
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
