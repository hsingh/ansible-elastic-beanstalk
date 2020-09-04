#!/usr/bin/python

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import boto3_conn, ec2_argument_spec, get_aws_connection_info, camel_dict_to_snake_dict
from botocore.exceptions import ClientError

try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

DOCUMENTATION = '''--- module: elasticbeanstalk_env short_description: create, update, delete beanstalk application 
environments description: - creates, updates, deletes beanstalk environments. options: app_name: description: - name 
of the beanstalk application you wish to manage the versions of required: true default: null env_name: description: - 
unique name for the deployment environment. Must be from 4 to 40 characters in length. The name can contain only 
letters, numbers, and hyphens. It cannot start or end with a hyphen. This name must be unique in your account. 
required: true default: null version_label: description: - label of the version you want to deploy in the environment 
required: false default: null description: description: - describes this environment required: false default: null 
wait_timeout: description: - Number of seconds to wait for an environment to change state. required: false default: 
900 template_name: description: - name of the configuration template to use in deployment. You must specify either 
this parameter or a solution_stack_name required: false default: null solution_stack_name: description: - this is an 
alternative to specifying a template_name. You must specify either this or a template_name, but not both required: 
false default: null cname_prefix: description: - if specified, the environment attempts to use this value as the 
prefix for the CNAME. If not specified, the environment uses the environment name. required: false default: null 
option_settings: description: - 'A dictionary array of settings to add of the form: { Namespace: ..., OptionName: ... 
, Value: ... }. If specified, AWS Elastic Beanstalk sets the specified configuration options to the requested value 
in the configuration set for the new environment. These override the values obtained from the solution stack or the 
configuration template' required: false default: null tags: description: - A dictionary of Key/Value tags to apply to 
the environment on creation. Tags cannot be modified once the environment is created. required: false default: null 
tier_name: description: - name of the tier required: false default: WebServer choices: ['WebServer', 'Worker'] state: 
description: - whether to ensure the environment is present or absent, or to list existing environments required: 
false default: present choices: ['absent','present','list','details'] 

author: Harpreet Singh
extends_documentation_fragment: aws
'''

EXAMPLES = '''
# Create or update environment
- elasticbeanstalk_env:
    region: us-east-1
    app_name: Sample App
    env_name: sampleApp-env
    version_label: Sample Application
    solution_stack_name: "64bit Amazon Linux 2014.09 v1.2.1 running Docker 1.5.0"
    option_settings:
      - Namespace: aws:elasticbeanstalk:application:environment
        OptionName: PARAM1
        Value: bar
      - Namespace: aws:elasticbeanstalk:application:environment
        OptionName: PARAM2
        Value: foobar
    tags:
      Name: Sample App
  register: env

# Delete environment
- elasticbeanstalk_env:
    app_name: Sample App
    env_name: sampleApp-env
    state: absent
    wait_timeout: 360
    region: us-west-2
'''

RETURN = '''
env:
    description: beanstalk environment
    returned: success and when state != list
    type: dict
    sample: {
        "AbortableOperationInProgress": false,
        "ApplicationName": "app-name",
        "CNAME": "app-name.p55wp6rh2e.us-west-2.elasticbeanstalk.com",
        "DateCreated": "2016-05-20T19:03:05.090000+00:00",
        "DateUpdated": "2016-12-09T16:23:55.915000+00:00",
        "EndpointURL": "awseb-e-g-AWSEBLoa-D0BNVCQMC73I-22790164.us-west-2.elb.amazonaws.com",
        "EnvironmentId": "e-g2jcgheahs",
        "EnvironmentLinks": [],
        "EnvironmentName": "app-name-qa",
        "Health": "Green",
        "SolutionStackName": "64bit Amazon Linux 2016.03 v2.1.0 running Docker 1.9.1",
        "Status": "Ready",
        "Tier": {
            "Name": "WebServer",
            "Type": "Standard",
            "Version": "1.0"
        },
        "OptionSettings": [
            // included when state == detail
            {
                "Namespace": "aws:autoscaling:asg",
                "OptionName": "Availability Zones",
                "ResourceName": "AWSEBAutoScalingGroup",
                "Value": "Any"
            }
            ...
        ]
        "VersionLabel": "1.0.0"
    }
output:
    description: message indicating what change will occur
    returned: in check mode
    type: string
    sample: Environment is up-to-date
'''


def wait_for(ebs, app_name, env_name, wait_timeout, testfunc):
    timeout_time = time.time() + wait_timeout

    while True:
        try:
            env = describe_env(ebs, app_name, env_name, [])
        except Exception as error:
            raise error

        if testfunc(env):
            return env

        if time.time() > timeout_time:
            raise ValueError("The timeout has expired")

        time.sleep(15)


def version_is_updated(version_label, env):
    return version_label == "" or env["VersionLabel"] == version_label


def status_is_ready(env):
    return env["Status"] == "Ready"


def health_is_green(env):
    return env["Health"] == "Green"


def health_is_grey(env):
    return env["Health"] == "Grey"


def terminated(env):
    return env["Status"] == "Terminated"


def describe_env(ebs, app_name, env_name, ignored_statuses):
    environment_names = [] if env_name is None else [env_name]

    result = ebs.describe_environments(ApplicationName=app_name, EnvironmentNames=environment_names)
    envs = result["Environments"]

    if not isinstance(envs, list):
        return None

    for env in envs:
        if "Status" in env and env["Status"] in ignored_statuses:
            envs.remove(env)

    if len(envs) == 0:
        return None

    return envs if env_name is None else envs[0]


def describe_env_config_settings(ebs, app_name, env_name):
    result = ebs.describe_configuration_settings(ApplicationName=app_name, EnvironmentName=env_name)
    envs = result["ConfigurationSettings"]

    if not isinstance(envs, list):
        return None

    for env in envs:
        if "Status" in env and env["Status"] in ["Terminated", "Terminating"]:
            envs.remove(env)

    if len(envs) == 0:
        return None

    return envs if env_name is None else envs[0]


def update_required(ebs, env, params):
    updates = []
    if params["version_label"] and env["VersionLabel"] != params["version_label"]:
        updates.append(('VersionLabel', env['VersionLabel'], params['version_label']))

    if params.get("template_name", None) and not ("TemplateName" in env):
        updates.append(('TemplateName', None, params['template_name']))
    elif "TemplateName" in env and env["TemplateName"] != params["template_name"]:
        updates.append(('TemplateName', env['TemplateName'], params['template_name']))

    result = ebs.describe_configuration_settings(ApplicationName=params["app_name"],
                                                 EnvironmentName=params["env_name"])

    options = result["ConfigurationSettings"][0]["OptionSettings"]

    for setting in params["option_settings"]:
        change = new_or_changed_option(options, setting)
        if change is not None:
            updates.append(change)

    return updates


def new_or_changed_option(options, setting):
    for option in options:
        if option["Namespace"] == setting["Namespace"] and option["OptionName"] == setting["OptionName"]:

            if ((setting['Namespace'] in ['aws:autoscaling:launchconfiguration', 'aws:ec2:vpc'] and
                 setting['OptionName'] in ['SecurityGroups', 'ELBSubnets', 'Subnets'] and
                 set(setting['Value'].split(',')).issubset(setting['Value'].split(','))) or
                    ('Value' in option and option["Value"] == setting["Value"])):
                return None
            else:
                if 'Value' in option:
                    return f"{option['Namespace']}:{option['OptionName']}", option['Value'], setting['Value']

    return f"{setting['Namespace']}:{setting['OptionName']}", '<NEW>', setting['Value']


def check_env(ebs, app_name, env_name, module):
    state = module.params['state']
    env = describe_env(ebs, app_name, env_name, ["Terminated", "Terminating"])

    result = {}

    if state == 'present' and env is None:
        result = dict(changed=True, output="Environment would be created")
    elif state == 'present' and env is not None:
        updates = update_required(ebs, env, module.params)
        if len(updates) > 0:
            result = dict(changed=True, output="Environment would be updated", env=env, updates=updates)
        else:
            result = dict(changed=False, output="Environment is up-to-date", env=env)
    elif state == 'absent' and env is None:
        result = dict(changed=False, output="Environment does not exist")
    elif state == 'absent' and env is not None:
        result = dict(changed=True, output="Environment will be deleted", env=env)

    module.exit_json(**result)


def filter_empty(**kwargs):
    return {k: v for k, v in iter(kwargs.items()) if v}


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        app_name=dict(type='str', required=True),
        env_name=dict(type='str', required=False),
        version_label=dict(type='str', required=False),
        description=dict(type='str', required=False),
        state=dict(choices=['present', 'absent', 'list', 'details'], default='present'),
        wait_timeout=dict(default=900, type='int'),
        template_name=dict(type='str', required=False),
        solution_stack_name=dict(type='str', required=False),
        cname_prefix=dict(type='str', required=False),
        option_settings=dict(type='list', default=[]),
        tags=dict(type='dict', default=dict()),
        options_to_remove=dict(type='list', default=[]),
        tier_name=dict(default='WebServer', choices=['WebServer', 'Worker'])
    ),
    )
    module = AnsibleModule(argument_spec=argument_spec,
                           mutually_exclusive=[['solution_stack_name', 'template_name']],
                           supports_check_mode=True)

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    app_name = module.params['app_name']
    env_name = module.params['env_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']
    wait_timeout = module.params['wait_timeout']
    template_name = module.params['template_name']
    solution_stack_name = module.params['solution_stack_name']
    cname_prefix = module.params['cname_prefix']
    tags = module.params['tags']
    option_settings = module.params['option_settings']

    tier_type = 'Standard'
    tier_name = module.params['tier_name']

    if tier_name == 'Worker':
        tier_type = 'SQS/HTTP'

    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)
    if not region:
        module.fail_json(msg='region must be specified')
    ebs = boto3_conn(module, conn_type='client', resource='elasticbeanstalk',
                     region=region, endpoint=ec2_url, **aws_connect_params)

    update = False
    result = {}

    if state == 'list':
        try:
            env = describe_env(ebs, app_name, env_name, [])
            result = dict(changed=False, env=[] if env is None else env)
        except ClientError as error:
            module.fail_json(msg=str(error), **camel_dict_to_snake_dict(error.response))

    if state == 'details':
        try:
            env = describe_env_config_settings(ebs, app_name, env_name)
            result = dict(changed=False, env=env)
        except ClientError as error:
            module.fail_json(msg=str(error), **camel_dict_to_snake_dict(error.response))

    if module.check_mode and (state != 'list' or state != 'details'):
        check_env(ebs, app_name, env_name, module)
        module.fail_json(msg='ASSERTION FAILURE: check_version() should not return control.')

    if state == 'present':
        try:
            tags_to_apply = [{'Key': k, 'Value': v} for k, v in iter(tags.items())]
            ebs.create_environment(**filter_empty(ApplicationName=app_name,
                                                  EnvironmentName=env_name,
                                                  VersionLabel=version_label,
                                                  TemplateName=template_name,
                                                  Tags=tags_to_apply,
                                                  SolutionStackName=solution_stack_name,
                                                  CNAMEPrefix=cname_prefix,
                                                  Description=description,
                                                  OptionSettings=option_settings,
                                                  Tier={'Name': tier_name, 'Type': tier_type, 'Version': '1.0'}))

            env = wait_for(ebs, app_name, env_name, wait_timeout, status_is_ready)
            result = dict(changed=True, env=env)
        except ClientError as error:
            if 'Environment %s already exists' % env_name in str(error):
                update = True
            else:
                module.fail_json(msg=str(error), **camel_dict_to_snake_dict(error.response))

    if update:
        try:
            env = describe_env(ebs, app_name, env_name, [])
            updates = update_required(ebs, env, module.params)
            if len(updates) > 0:
                ebs.update_environment(**filter_empty(
                    EnvironmentName=env_name,
                    VersionLabel=version_label,
                    TemplateName=template_name,
                    Description=description,
                    OptionSettings=option_settings))

                env = wait_for(ebs, app_name, env_name, wait_timeout,
                               lambda environment: status_is_ready(environment) and version_is_updated(version_label,
                                                                                                       environment))

                result = dict(changed=True, env=env, updates=updates)
            else:
                result = dict(changed=False, env=env)
        except ClientError as error:
            module.fail_json(msg=str(error), **camel_dict_to_snake_dict(error.response))

    if state == 'absent':
        try:
            ebs.terminate_environment(EnvironmentName=env_name)
            env = wait_for(ebs, app_name, env_name, wait_timeout, terminated)
            result = dict(changed=True, env=env)
        except ClientError as error:
            if 'No Environment found for EnvironmentName = \'%s\'' % env_name in str(error):
                result = dict(changed=False, output='Environment not found')
            else:
                module.fail_json(msg=str(error), **camel_dict_to_snake_dict(e.response))

    module.exit_json(**result)


if __name__ == '__main__':
    main()
