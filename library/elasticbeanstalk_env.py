#!/usr/bin/python

DOCUMENTATION = '''
---
module: elasticbeanstalk_env
short_description: create, update, delete beanstalk application environments
description:
    - creates, updates, deletes beanstalk environments.
options:
  app_name:
    description:
      - name of the beanstalk application you wish to manage the versions of
    required: true
    default: null
  env_name:
    description:
      - unique name for the deployment environment. Must be from 4 to 23 characters in length. The name can contain only letters, numbers, and hyphens. It cannot start or end with a hyphen. This name must be unique in your account.
    required: true
    default: null
  version_label:
    description:
      - label of the version you want to deploy in the environment
    required: false
    default: null
  description:
    description:
      - describes this environment
    required: false
    default: null
  wait_timeout:
    description:
      - Number of seconds to wait for an environment to change state.
    required: false
    default: 900
  template_name:
    description:
      - name of the configuration template to use in deployment. You must specify either this parameter or a solution_stack_name
    required: false
    default: null
  solution_stack_name:
    description:
      - this is an alternative to specifying a template_name. You must specify either this or a template_name, but not both
    required: false
    default: null
  cname_prefix:
    description:
      - if specified, the environment attempts to use this value as the prefix for the CNAME. If not specified, the environment uses the environment name.
    required: false
    default: null
  option_settings:
    description:
      - 'A dictionary array of settings to add of the form: { Namespace: ..., OptionName: ... , Value: ... }. If specified, AWS Elastic Beanstalk sets the specified configuration options to the requested value in the configuration set for the new environment. These override the values obtained from the solution stack or the configuration template'
    required: false
    default: null
  tier_name:
    description:
      - name of the tier
    required: false
    default: WebServer
    choices: ['WebServer', 'Worker']
  state:
    description:
      - whether to ensure the environment is present or absent, or to list existing environments
    required: false
    default: present
    choices: ['absent','present','list']

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
  register: env

# Delete environment
- elasticbeanstalk_env:
    app_name: Sample App
    env_name: sampleApp-env
    state: absent
    wait_timeout: 360
    region: us-west-2
'''

try:
    import boto.beanstalk
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

IGNORE_CODE = "Throttling"
def wait_for(ebs, app_name, env_name, wait_timeout, testfunc):
    timeout_time = time.time() + wait_timeout

    while True:
        try:
            env = describe_env(ebs, app_name, env_name)
        except boto.exception.BotoServerError, e:
            if e.code != IGNORE_CODE:
                raise e

        if testfunc(env):
            return env

        if time.time() > timeout_time:
            raise ValueError("The timeout has expired")

        time.sleep(15)

def health_is_green(env):
    return env["Health"] == "Green"

def health_is_grey(env):
    return env["Health"] == "Grey"

def terminated(env):
    return env["Status"] == "Terminated"

def describe_env(ebs, app_name, env_name):
    environment_names = [env_name] if env_name is not None else None

    result = ebs.describe_environments(application_name=app_name, environment_names=environment_names)
    envs = result["DescribeEnvironmentsResponse"]["DescribeEnvironmentsResult"]["Environments"]

    if not isinstance(envs, list): return None

    for env in envs:
        if env.has_key("Status") and env["Status"] in ["Terminated","Terminating"]:
            envs.remove(env)

    if len(envs) == 0: return None

    return envs if env_name is None else envs[0]

def update_required(ebs, env, params):
    updates = []
    if params["version_label"] and env["VersionLabel"] != params["version_label"]:
        updates.append(('VersionLabel', env['VersionLabel'], params['version_label']))

    if env["TemplateName"] != params["template_name"]:
        updates.append(('TemplateName', env['TemplateName'], params['template_name']))

    result = ebs.describe_configuration_settings(application_name=params["app_name"],
                                                 environment_name=params["env_name"])

    options = result["DescribeConfigurationSettingsResponse"]["DescribeConfigurationSettingsResult"]["ConfigurationSettings"][0]["OptionSettings"]

    for setting in params["option_settings"]:
        change = new_or_changed_option(options, setting)
        if change is not None:
            updates.append(change)

    return updates

def new_or_changed_option(options, setting):
    for option in options:
        if option["Namespace"] == setting["Namespace"] and \
            option["OptionName"] == setting["OptionName"]:

            if (setting['Namespace'] in ['aws:autoscaling:launchconfiguration','aws:ec2:vpc'] and \
                setting['OptionName'] in ['SecurityGroups', 'ELBSubnets', 'Subnets'] and \
                set(setting['Value'].split(',')).issubset(option['Value'].split(','))) or \
                option["Value"] == setting["Value"]:
                return None
            else:
                return (option["Namespace"] + ':' + option["OptionName"], option["Value"], setting["Value"])

    return (setting["Namespace"] + ':' + setting["OptionName"], "<NEW>", setting["Value"])

def boto_exception(err):
    '''generic error message handler'''
    if hasattr(err, 'error_message'):
        error = err.error_message
    elif hasattr(err, 'message'):
        error = err.message
    else:
        error = '%s: %s' % (Exception, err)

    return error

def check_env(ebs, app_name, env_name, module):
    state = module.params['state']
    env = describe_env(ebs, app_name, env_name)

    result = {}

    if state == 'present' and env is None:
        result = dict(changed=True, output = "Environment would be created")
    elif state == 'present' and env is not None:
        updates = update_required(ebs, env, module.params)
        if len(updates) > 0:
            result = dict(changed=True, output = "Environment would be updated", env=env, updates=updates)
        else:
            result = dict(changed=False, output="Environment is up-to-date", env=env)
    elif state == 'absent' and env is None:
        result = dict(changed=False, output="Environment does not exist")
    elif state == 'absent' and env is not None:
        result = dict(changed=True, output="Environment will be deleted", env=env)

    module.exit_json(**result)


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
            app_name       = dict(required=True),
            env_name       = dict(),
            version_label  = dict(),
            description    = dict(),
            state          = dict(choices=['present','absent','list'], default='present'),
            wait_timeout   = dict(default=900, type='int'),
            template_name  = dict(),
            solution_stack_name = dict(),
            cname_prefix = dict(),
            option_settings = dict(type='list',default=[]),
            options_to_remove = dict(type='list',default=[]),
            tier_name = dict(default='WebServer', choices=['WebServer','Worker'])
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec,
                           mutually_exclusive=[['solution_stack_name','template_name']],
                           supports_check_mode=True)

    if not HAS_BOTO:
        module.fail_json(msg='boto required for this module')

    app_name = module.params['app_name']
    env_name = module.params['env_name']
    version_label = module.params['version_label']
    description = module.params['description']
    state = module.params['state']
    wait_timeout = module.params['wait_timeout']
    template_name = module.params['template_name']
    solution_stack_name = module.params['solution_stack_name']
    cname_prefix = module.params['cname_prefix']
    option_settings = module.params['option_settings']
    options_to_remove = module.params['options_to_remove']

    tier_type = 'Standard'
    tier_name = module.params['tier_name']

    if tier_name == 'Worker':
        tier_type = 'SQS/HTTP'

    option_setting_tups = [(os['Namespace'],os['OptionName'],os['Value']) for os in option_settings]
    option_to_remove_tups = [(otr['Namespace'],otr['OptionName']) for otr in options_to_remove]


    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module)

    try:
        ebs = boto.beanstalk.connect_to_region(region)

    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg='No Authentication Handler found: %s ' % str(e))
    except Exception, e:
        module.fail_json(msg='Failed to connect to Beanstalk: %s' % str(e))


    update = False
    result = {}

    if state == 'list':
        try:
            env = describe_env(ebs, app_name, env_name)
            result = dict(changed=False, env=env)
        except Exception, err:
            error_msg = boto_exception(err)
            module.fail_json(msg=error_msg)

    if module.check_mode and state != 'list':
        check_env(ebs, app_name, env_name, module)
        module.fail_json('ASSERTION FAILURE: check_version() should not return control.')

    if state == 'present':
        try:
            ebs.create_environment(app_name, env_name, version_label, template_name,
                              solution_stack_name, cname_prefix, description,
                              option_setting_tups, None, tier_name,
                              tier_type, '1.0')

            env = wait_for(ebs, app_name, env_name, wait_timeout, health_is_green)
            result = dict(changed=True, env=env)
        except Exception, err:
            error_msg = boto_exception(err)
            if 'Environment %s already exists' % env_name in error_msg:
                update = True
            else:
                module.fail_json(msg=error_msg)


    if update:
        try:
            env = describe_env(ebs, app_name, env_name)
            updates = update_required(ebs, env, module.params)
            if len(updates) > 0:
                ebs.update_environment(environment_name=env_name,
                                       version_label=version_label,
                                       template_name=template_name,
                                       description=description,
                                       option_settings=option_setting_tups,
                                       options_to_remove=None)

                wait_for(ebs, app_name, env_name, wait_timeout, health_is_grey)
                env = wait_for(ebs, app_name, env_name, wait_timeout, health_is_green)

                result = dict(changed=True, env=env, updates=updates)
            else:
                result = dict(changed=False, env=env)

        except Exception, err:
            error_msg = boto_exception(err)
            module.fail_json(msg=error_msg)

    if state == 'absent':
        try:
            ebs.terminate_environment(environment_name=env_name)
            env = wait_for(ebs, app_name, env_name, wait_timeout, terminated)
            result = dict(changed=True, env=env)
        except Exception, err:
            error_msg = boto_exception(err)
            if 'No Environment found for EnvironmentName = \'%s\'' % env_name in error_msg:
                result = dict(changed=False, output='Environment not found')
            else:
                module.fail_json(msg=error_msg)

    module.exit_json(**result)


# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
