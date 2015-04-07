#!/usr/bin/python

DOCUMENTATION = '''
---
module: elasticbeanstalk_env
short_description: Ansible module for managing beanstalk environments
'''

try:
    import boto.beanstalk
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

def wait_for_health(ebs, app_name, env_name, health, wait_timeout):
    VALID_BEANSTALK_HEALTHS = ('Green', 'Yellow', 'Red', 'Grey')

    if not health in VALID_BEANSTALK_HEALTHS:
        raise ValueError(health + " is not a valid beanstalk health value")

    timeout_time = time.time() + wait_timeout

    while 1:
        #print "Waiting for beanstalk %s to turn %s" % (app_name, health)

        result = ebs.describe_environments(application_name=app_name, environment_names=[env_name])
        current_health = result["DescribeEnvironmentsResponse"]["DescribeEnvironmentsResult"]["Environments"][0]["Health"]
        #print "Current health is: %s" % current_health

        if current_health == health:
            #print "Beanstalk %s has turned %s" % (app_name, health)
            return result

        if time.time() > timeout_time:
            raise ValueError("The timeout has expired")

        time.sleep(15)

def filter_terminated(env):
    return env["Status"] != 'Terminated'

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
            app_name       = dict(required=True),
            env_name       = dict(required=True),
            version_label  = dict(required=True),
            description    = dict(),
            state          = dict(choices=['present','absent'], default='present'),
            wait_timeout   = dict(default=300)
        ),
    )
    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_BOTO:
        module.fail_json(msg='boto required for this module')

    app_name = module.params.get('app_name')
    env_name = module.params.get('env_name')
    version_label = module.params.get('version_label')
    if module.params.get('description'):
        description = module.params.get('description')

    state = module.params.get('state')
    wait_timeout = module.params.get('wait_timeout')

    result = {}
    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module)

    try:
        ebs = boto.beanstalk.connect_to_region(region)

    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg='No Authentication Handler found: %s ' % str(e))
    except Exception, e:
        module.fail_json(msg='Failed to connect to Beanstalk: %s' % str(e))


    envs = ebs.describe_environments(app_name, version_label=None, environment_names=[env_name])

    envs = filter(filter_terminated, envs["DescribeEnvironmentsResponse"]["DescribeEnvironmentsResult"]["Environments"])

    if state == 'present':
        if len(envs) == 1:
            if envs[0]["VersionLabel"] == version_label:
                result = dict(changed=False, env=envs[0])
            else:
                updRequest = ebs.update_environment(environment_name=env_name,
                                        version_label=version_label)

                wait_for_health(ebs, app_name, env_name, 'Grey', wait_timeout)
                envs = wait_for_health(ebs, app_name, env_name, 'Green', wait_timeout)

                envs = envs["DescribeEnvironmentsResponse"]["DescribeEnvironmentsResult"]["Environments"]
                result = dict(changed=True, env=envs[0])
        else:
            result = dict(changed=False, output='Environment not found')
    else:
        result = dict(changed=False, output='Environment removal not supported')

    #     if len(envs) == 1:
    #         ebs.terminate_environment(environment_name=env_name)
    #         result = dict(changed=True, output='Environment deleted')
    #         module.exit_json(**result)
    #     else:
    #         result = dict(changed=True, output='Environment not found')
    #         module.exit_json(**result)

    module.exit_json(**result)


# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
