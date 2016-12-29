# Changelog

#### 2.0.0 December 29 2016
- Upgraded all modules to boto3, now requires Ansible >= 2.0

#### 0.9.1 October 26 2016
- Fix bug in environment version update check

#### 0.9 March 23 2016
- Verify version change after deployment
- Add details operation for beanstalk environments
- Use status instead of health

#### 0.8.2 June 19 2015
- Fix bug in listing

#### 0.8.1 June 15 2015
- Remove incorrect quote character in 0.8

#### 0.8 June 5 2015
- Ignore terminating or terminated environments when listing

#### 0.7 May 7 2015
- Skip version change if version_label is not provided

#### 0.6 May 5 2015
- Add support for getting details of multiple environments

#### 0.5 April 30 2015
- Add support for check mode

#### 0.4 April 21 2015
- Add option to list beanstalk environments

#### 0.3 April 16 2015
- Add support for create, update, delete beanstalk environments
- Improved change detection for beanstalk environments
- Increase default timeout to 900 seconds

#### 0.2 April 7 2015
- Fix issue with wait timeout
- Add ability to application version delete source bundle

#### 0.1 - April 7 2015
- Initial version
