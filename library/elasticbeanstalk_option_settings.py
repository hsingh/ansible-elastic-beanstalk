
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
