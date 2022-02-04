#!/usr/bin/env python3

import sys
import os
import signal
import socket
from packaging import version # version.parse()
import re
import operator
import fcntl
import locale
import subprocess
import select
import queue
import threading

# append to the interpreter’s search path for modules
directory = "/var/lib/lernstick-exam-client/persistent/var/lib/lernstick-exam-client"
sys.path.append(directory)
import functions as helpers # 

# Constants
envFile = "/etc/lernstick-exam-client-env.conf"
lockFile = "/run/lock/lernstick-exam-client-search.lock"
retoreStateFile = "/run/initramfs/restore"
urlWhitelistFile = "/etc/lernstick-firewall/url_whitelist"
infoFile = "/run/initramfs/info"
configFile = "/etc/lernstick-exam-client.conf"
DEBUG = True

# translations
messages = {
    'de': {
        'Search': 'Suche',
        'Searching for exam server.': 'Suche nach Prüfungsserver.',
    }
}

# the language code
lang = locale.getdefaultlocale()[0].split('_')[0] # eg: de, en, es, ...

# translation function
def _(string, lang = lang):
    if lang in messages and string in messages[lang]:
        return messages[lang][string]
    else:
        return string

# Obtains a variable in key=value-format from a file
# @param string variable the name of the variable
# @param string file filename
# @return string the value or the empty string
def getVariableFromFile(variable, file):
    with open(file, "r") as fh:
        for line in fh:
            try:
                key, value = line.split("=", 2)
                if key == variable:
                    return value.strip('"\'\n ')
            except: pass            
    return ''

# Obtains all variables in key=value-format from a file
def getVariablesFromFile(file, r = {}):
    with open(file, "r") as fh:
        for line in fh:
            try:
                key, value = line.split("=", 2)
                if key != '':
                    r[key.strip('"\'\n ')] = value.strip('"\'\n ')
            except: pass
    return r

def isDeb9OrNewer():
    v = int(getVariableFromFile('VERSION_ID', '/etc/os-release'))
    return not (v != '' and v <= 8)

# @param string ver version string to compare
# @param string wants compare ver with this (eg: <=1.2.3)
def check_version(ver, wants):
    r = re.search('([\>,\<,\=]+)([0-9,\.]+)', wants)
    p = lambda v: version.parse(v)
    if r:
        operator = r.group(1)
        ver2 = r.group(2)
    else:
        operator = '=='
        ver2 = wants

    return (
        (operator == '==' and p(ver) == p(ver2))
        or (operator == '<=' and p(ver) <= p(ver2))
        or (operator == '>=' and p(ver) >= p(ver2))
        or (operator == '<'  and p(ver) <  p(ver2))
        or (operator == '>'  and p(ver) >  p(ver2))
        or False
    )

# Handles any cleanup
def clean_exit(reason = None):
    print('Exiting gracefully (reason: {0})'.format(reason), file = sys.stderr)

    # revert all changes to iptables
    helpers.run('iptables-save | grep -v "searchExamServer" | iptables-restore -w')
    helpers.run('iptables-legacy-save | grep -v "searchExamServer" | iptables-legacy-restore -w')

    # if isDeb9OrNewer():
    #     url_whitelist = helpers.run('diff --unchanged-group-format="" <(echo "^{p}://{h}" | sed "s/\./\\\./g") {f}'.format(f = urlWhitelistFile, p = gladosProto, h = gladosHost))
    # else:
    #     url_whitelist = helpers.run('diff --unchanged-group-format="" <(echo "^{p}://{h}") {f}'.format(f = urlWhitelistFile, p = gladosProto, h = gladosHost))

    helpers.run('umount /run/initramfs/newroot 2>/dev/null')
    helpers.run('umount -l /run/initramfs/{base,exam} 2>/dev/null')

    if isDeb9OrNewer(): helpers.run('squid -k reconfigure') # iptables stays

    exit(0)

def trap(signal_received, frame):
    clean_exit('signal {0} recieved'.format(signal_received))

def file_get_contents(file):
    with open(file) as f:
        return f.read()

def decimals_to_hex(line):
    r = re.sub(r'\\(\d+)', lambda m: '\\x{:x}'.format(int(m.group(1))), line)
    return str.encode(r).decode('unicode_escape')

# Enqueues the stdout of a process and return a "new" readline function that takes a timeout
# @param Popen process the process object returned by subprocess.Popen()
# @return callable readline function with the following structure:
#       @param Queue q queue object to append to, when a line is read
#       @param float timeout
#       @return str|False the line or False if timed out
def enqueue_process(process):
    q = queue.Queue()
    def enqueue_output(out, queue):
        for line in iter(out.readline, b''):
            queue.put(line)
        out.close()

    def readline(timeout = 0.1):
        if timeout == 0:
            get = lambda: q.get_nowait()
        else:
            get = lambda: q.get(timeout = timeout)
        try: line = get()
        except queue.Empty: # no output yet
            return False
        else: # got line
            return line

    t = threading.Thread(target = enqueue_output, args = (process.stdout, q))
    t.daemon = True # thread dies with the program
    t.start()
    return readline

if __name__ == '__main__':
    # print(getVariableFromFile('VERSION_ID', '/etc/os-release'))
    # print(isDeb9OrNewer())
    # print(check_version('1', '==2'))
    # print(check_version('1', '2'))
    # print(check_version('1', '<=2'))
    # print(check_version('1', '>=2'))
    # print(check_version('1', '<2'))
    # print(check_version('1', '>2'))

    # Exit if already running
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('localhost', 18493))
    except OSError:
        print('Program is already running, exitting.', file = sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGINT, trap)
    signal.signal(signal.SIGTERM, trap)

    # import time
    # time.sleep(10)

    # allow bonjour/zeroconf
    helpers.run('iptables -I INPUT -p udp --dport 5353 -d 224.0.0.251 -m comment --comment "searchExamServer" -j ACCEPT')
    helpers.run('iptables -I OUTPUT -p udp --dport 5353 -d 224.0.0.251 -m comment --comment "searchExamServer" -j ACCEPT')

    display = helpers.get_env("DISPLAY")
    xauthority = helpers.get_env("XAUTHORITY")
    env = {
        'DISPLAY': display,
        'XAUTHORITY': xauthority,
        'LANG': helpers.get_env('LANG')
    }

    # create the directory structure and cleanup
    for path in ['newroot','base','exam','tmpfs','squashfs','backup/home/user']:
        os.makedirs('/run/initramfs/' + path, exist_ok = True)
    os.chown('/run/initramfs/backup/home/user', 1000, 1000) # @todo evtl. shutil.chown() accepts names
    if os.path.exists(retoreStateFile): os.remove(retoreStateFile)

    if os.path.isfile(infoFile) and os.access(infoFile, os.R_OK):
        glados_info = getVariablesFromFile(infoFile)
        #print(glados_info)

    # if a configfile is used, don't display a selection list and use the config values instead
    if os.path.isfile(configFile) and os.access(configFile, os.R_OK):
        fixed = True

        # starting subprocess
        cmd = 'zenity --progress --pulsate --no-cancel --title="{title}" --text="{text}" --auto-close'.format(
            title = _('Search'),
            text = _('Searching for exam server.'),
        )
        zenity = subprocess.Popen(cmd, env = env, shell = True, stdin = subprocess.PIPE)

        if DEBUG: print("Configfile found, using {}.".format(configFile))
        glados_info = getVariablesFromFile(configFile, glados_info)

        avahi = file_get_contents(configFile)

        eth, _ = helpers.run("$(ip -s route get {gladosIp} | perl -ne 'print $1 if /dev[\s]+([^\s]+)/')".format(**glados_info))

        # ending subprocess
        # dont end here, end there https://github.com/Lernstick/lernstick-exam-client/blob/master/usr/bin/searchExamServer#L312
        #stdout = zenity.communicate(input = b'100')[0] # 

    else:
        fixed = False
        choice = False

        while choice == False:

            # show the selection list until the user has chosen one
            zenity_cmd = ('zenity --list '
                    + '--title="{title}" '
                    + '--text="{text}" '
                    + '--column "#" '
                    + '--column "{name}" '
                    + '--column "{ip}" '
                    + '--column "{host}" '
                    + '--column "{port}" '
                    + '--column "{protocol}" '
                    + '--column "{interface}" '
                    + '--hide-column=1 '
                    + '--width=700 '
                    + '--height=220').format(
                title = _('Searching for exam server.'),
                text = _('The following list of exam servers was found in the network. Please select the one you want to use.'),
                name = _('Name'),
                ip = _('IP'),
                host = _('Host'),
                port = _('Port'),
                protocol = _('Protocol'),
                interface = _('Interface')
            )
            #zenity_cmd = 'zenity --progress --no-cancel --auto-close'
            zenity_process = subprocess.Popen(zenity_cmd, env = env, shell = True, stdin = subprocess.PIPE, stdout = subprocess.PIPE)
            avahi_cmd = 'avahi-browse -rp --no-db-lookup -a'
            avahi_process = subprocess.Popen(avahi_cmd, env = env, shell = True,
                stdin = subprocess.PIPE,
                stdout = subprocess.PIPE,
                bufsize = 1 # line buffered
            )
            #avahi_process = subprocess.Popen('for i in $(seq 1 100); do sleep 0.02; echo $i; done', env = env, shell = True, stdin = subprocess.PIPE, stdout = subprocess.PIPE)

            readline = enqueue_process(avahi_process) # "improved" readline that can take a timeout argument

            n = 1
            while True:
                line = readline(0.1)
                if line == False:
                    if zenity_process.poll() != None: # process has ended
                        if zenity_process.returncode != 0:
                            clean_exit('User aborted zenity')
                        else:
                            break
                    if avahi_process.poll() != None:
                        break
                else:
                    line = line.rstrip().decode("utf-8") + '\n'
                    pieces = line.split(';')
                    if len(pieces) >= 10:
                        if pieces[0] == '=' and pieces[2] == 'IPv4' and 'Glados' in pieces[9]:

                            output_line = '{number}\n{name}\n{ip}\n{host}\n{port}\n{protocol}\n{interface}\n'.format(
                                number = n,
                                name = pieces[3],
                                ip = pieces[7],
                                host = pieces[6],
                                port = pieces[8],
                                protocol = 'https' if pieces[4] == '_https._tcp' else 'http',
                                interface = pieces[1]
                            )

                            output_line = decimals_to_hex(output_line)
                            zenity_process.stdin.write(str.encode(output_line))
                            zenity_process.stdin.flush()
                            n += 1


            zenity_output = zenity_process.communicate()[0].rstrip().decode("utf-8")
            choice = zenity_output if zenity_output != '' else False
            zenity_process.stdin.close()
            zenity_process.terminate()
            avahi_process.stdin.close()
            avahi_process.terminate()

    print("zenity choice", choice)
    clean_exit()
