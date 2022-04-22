#!/usr/bin/env python3

import json
import sys
import re
import os
import base64

# append to the interpreter’s search path for modules
directory = "/var/lib/lernstick-exam-client/"
sys.path.append(directory)
import functions as helpers # get_config(), get_info(), get_env(), run()

filter_wm_classes = ['hand-in-exam.hand-in-exam']
icon_size = "16x16"
icon_fmt = "gif"
icon_cmd = "xprop -id {window_id} -notype 32c _NET_WM_ICON | perl -0777 -pe '@_=/\d+/g; printf \"P7\\nWIDTH %d\\nHEIGHT %d\\nDEPTH 4\\nMAXVAL 255\\nTUPLTYPE RGB_ALPHA\\nENDHDR\\n\", splice@_,0,2; $_=pack \"N*\", @_; s/(.)(...)/$2$1/gs' | convert - -geometry \"{icon_size}\" {icon_fmt}:-"
max_list = 5

# create an array of dicts from data by splitting at newlines
# and creating a table indexed by columns.
def lines_to_dict(data, columns):
    l = []
    lines = data.splitlines()
    for line in lines:
        values = line.split(None, len(columns)-1)
        l.append(dict(zip(columns, values)))
    return l

# retrieve all the icons of open windows in base64
def get_icons(window_ids):
    icons = []
    for window_id in window_ids:
        if window_id != -1:
            _, icon = helpers.run(icon_cmd.format(
                window_id = window_id,
                icon_size = icon_size,
                icon_fmt = icon_fmt
            ), env = os.environ, encoding = None)
            icons.append(base64.b64encode(icon).decode('utf-8'))
        else:
            icons.append('')
    return icons

if __name__ == '__main__':
    os.chdir('/tmp') # convert creates temporary files on the current working directory
    retval, output = helpers.run('wmctrl -lpx', env = os.environ)
    window_list = lines_to_dict(output, ['window_id', 'desktop_nr', 'pid', 'wm_class', 'client_name', 'window_name'])
    window_list = list(filter(lambda d: d['wm_class'] not in filter_wm_classes, window_list))
    n = len(window_list)
    if n > max_list:
        window_list = window_list[0:max_list]
        window_list.append({'window_id': -1, 'window_name': n-max_list})
    icon_list = get_icons([d['window_id'] for d in window_list])

    j = {
        'windows': [d['window_name'] for d in window_list],
        'icons': icon_list,
    }

    print(json.dumps(j))
