elastic-beanstalk
=========

Ansible modules for working with Amazon Elastic Beanstalk

Requirements
------------

This module requires [boto](https://github.com/boto/boto)


Example Playbook
----------------

The example playbook demonstrates how to create an application and version and update an existing environment.

    ---
    - hosts: localhost
      connection: local
      gather_facts: False

      tasks:

      - name: Create Elastic Beanstalk application
        elasticbeanstalk_app:
          region: us-east-1
          app_name: Sample App
          state: present
        register: app

      - debug: var=app


      - name: Create application version
        elasticbeanstalk_version:
          region: us-east-1
          app_name: Sample App
          version_label: Sample Version
          s3_bucket: sample-app-versions-bucket
          s3_key: sample-version-1.0.0.zip
          state: present
        register: version

      - debug: var=version


      - name: Update environment
        elasticbeanstalk_env:
          region: us-east-1
          app_name: Sample App
          env_name: sampleapp-env
          version_label: Sample Version
        register: env

      - debug: var=env


License
-------

MIT

Author Information
------------------

[Harpreet Singh](http://about.me/hs)
