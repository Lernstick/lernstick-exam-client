#!/usr/bin/env python3
#
# The setup done script that asks whether to continue or wait
#

import argparse
import sys
import requests
import logging

# append to the interpreter’s search path for modules
directory = "/var/lib/lernstick-exam-client/persistent/var/lib/lernstick-exam-client"
sys.path.append(directory)
import functions as helpers # 

infoFile = "/run/initramfs/info"

# obtain the url, kwargs is for http.get()
def http_get(url, **kwargs):
    try:
        r = requests.get(url, **kwargs)
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        logger.error(repr(e))
        r = requests.models.Response()
        r.status_code = -1
        r.code = str(e)
        r.error_type = repr(e)
    return r

# grab all UUIDs from physical ethernet connections to bring them down before rebooting the
# system. This forces network-manager to reconnect each of them. This solves a problem when
# the system recieves an IP-address at bootup (by ipconfig) and NM handles it as "manual" IP.
# We don't loose DNS servers and the DHCP lease will be renewed properly.
def stop_interfaces(env):
    _, eths = helpers.run('nmcli -t -f state,type,con-uuid d status', env = env)
    for line in eths.splitlines():
        state, eth_type, name = line.split(':')
        if state == 'connected' and eth_type == 'ethernet':
            helpers.run(f'nmcli connection down uuid "{name}"', env = env)

if __name__ == '__main__':
    # parse the command line arguments
    parser = argparse.ArgumentParser(description = "script that asks whether to continue or wait")
    parser.add_argument('-d', '--debug', help = 'enable debugging', default = False, action = "store_true" )
    args = parser.parse_args()

    # setup logging
    logger = logging.getLogger("root") # create a logger called root
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
    ch = logging.StreamHandler() # create console handler
    ch.setFormatter(helpers.TerminalColorFormatter()) # formatter of console handler
    logger.addHandler(ch) # add handlers to logger
    logging.captureWarnings(True) # also capture warnings from other libs

    env = {
        'DISPLAY': helpers.get_env('DISPLAY'),
        'XAUTHORITY': helpers.get_env('XAUTHORITY')
    }

    cenv = {**env, **{'LC_ALL': 'C'}} 
    urlNotify = helpers.get_info("urlNotify", infoFile)

    if args.debug:
        zcmd = helpers.zenity(**{
            'question': True,
            'width': 300,
            'title': 'Continue',
            'text': 'The system setup is done. Continue?'
        })
        if helpers.run(zcmd, env = env)[0]:
            http_get(urlNotify.format(state = 'continue bootup'))
            stop_interfaces(cenv)
            helpers.run('halt')
    else:
        # timeout for 10 seconds
        zcmd = helpers.zenity(**{
            'progress': True,
            'no_cancel': True,
            'width': 300,
            'title': 'Continue',
            'text': 'The system will continue in 10 seconds',
            'percentage': 0,
            'auto_close': True
        })

        loop_cmd = 'for i in {{1..10}}; do echo "${{i}}0"; sleep 1; done | {zcmd}'.format(zcmd = zcmd)
        helpers.run(loop_cmd, env = env)
        http_get(urlNotify.format(state = 'continue bootup'))
        stop_interfaces(cenv)
        helpers.run('halt')
