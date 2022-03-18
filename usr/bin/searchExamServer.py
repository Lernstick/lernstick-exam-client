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
import json
import shutil # shell commands like cp, ...
import shlex # quote() strings for shell command
import time # time.sleep()
import requests # requests.get()
import http as ht # http.client
from requests.adapters import HTTPAdapter, Retry

# append to the interpreter’s search path for modules
directory = "/var/lib/lernstick-exam-client/persistent/var/lib/lernstick-exam-client"
sys.path.append(directory)
import functions as helpers # 

# Constants
DEBUG = True
LANGUAGE_TRANSLATION = False # Set to True to translate messages
envFile = "/etc/lernstick-exam-client-env.conf"
lockFile = "/run/lock/lernstick-exam-client-search.lock"
retoreStateFile = "/run/initramfs/restore"
urlWhitelistFile = "/etc/lernstick-firewall/url_whitelist"
infoFile = "/run/initramfs/info"
configFile = "/etc/lernstick-exam-client.conf"
compatFile = "/usr/share/lernstick-exam-client/compatibility.json"
actions = ['Download', 'Finish', 'Notify', 'SSHKey', 'Md5', 'Config']
glados_infos = ['gladosHost', 'gladosPort', 'gladosIp', 'gladosDesc', 'gladosProto']
variables = glados_infos + ['action'+i for i in actions]

# translations
messages = {
    "de": {
        "Search": "Suche",
        "Searching for exam server.": "Suche nach Prüfungsserver.",
        "The following list of exam servers was found in the network. Please select the one you want to use.": "Die folgende Liste von Prüfungsservern wurde im Netzwerk gefunden. Bitte wählen Sie denjenigen aus, den Sie verwenden möchten.",
        "Name": "Name",
        "IP": "IP",
        "Host": "Host",
        "Port": "Port",
        "Protocol": "Protokoll",
        "Interface": "Schnittstelle",
        "Exam server found.": "Prüfungsserver gefunden.",
        "Please wait": "Bitte warten",
        "Connecting to server.": "Verbinde zu Server",
        "Configuring firewall": "Firewall wird konfiguriert",
        "Fetching SSH key": "SSH Schüssel wird abgerufen",
        "Fetching server information": "Server Informationen werden abgerufen",
        "Checking versions": "Versionen werden überprüft",
        "Server version mismatch. Got {ver}, but client needs {wants}.": "Serverversionskonflikt: Hat {ver}, aber der Client fordert {wants}.",
        "Client version mismatch. Got {ver}, but server needs {wants}.": "Clientversionskonflikt: Hat {ver}, aber der Server fordert {wants}.",
        "Setting up token request": "Tokeneingabe wird vorbereitet",
        "Exam Client": "Prüfungsclient",
        "Taking Glados server from configuration file.": "Nehme Glados Srver von der Konfigurations Datei.",
        "Continue": "Fortfahren",
        "An exam server was found in the configuration file (via {interface}):\n\n    Desciption: {gladosDesc}\n    Hostname: {gladosHost}\n    IP: {gladosIp}\n\nSwitch to exam mode?": "Ein Prüfungsserver wurde in der Konfigurationdatei gefunden (via {interface}):\n\n    Beschreibung: {gladosDesc}\n    Hostname: {gladosHost}\n    IP: {gladosIp}\n\nIn den Prüfungsmodus wechseln?",
        "Error": "Fehler",
        "Failed to fetch the SSH key from Glados server.": "Abrufen des SSH Schlüssels fehlgeschlagen.",
        "Cannot obtain current Lernstick version.": "Aktuelle Lernstick Version kann nicht ermittelt werden.",
        "Cannot open compatibility file {path}": "Kompatibilitätsdatei {path} kann nicht geöffnet werden",
        "Unable to fetch Glados server version information.": "Glados Server Informationen können nicht abgerufen werden.",
        "Variable {var} not given in configuration file {file}. Please add this variable to the configuration file.": "Die Variable {var} is nicht in der Konfigurationdatei {file}. Bitte fügen Sie die Variable zur Konfigurationdatei hinzu.",
        "The Glados server ({gladosDesc}, {gladosHost}, {gladosIp}) configured in the configuration file {file} is not reachable via your network connection(s). Aborting.": "Der Glados Server ({gladosDesc}, {gladosHost}, {gladosIp}) aus der Konfigurationdatei {file} kann nicht über eine Ihrer Netzwerkverbindungen erreicht werden. Breche ab.",
        "Choice is invalid.": "Die Wahl is ungültig.",
        "Glados host not found.": "Glados Host nicht gefunden."
    }
}

env = {
    'DISPLAY': helpers.get_env("DISPLAY"),
    'XAUTHORITY': helpers.get_env("XAUTHORITY"),
    'LANG': helpers.get_env('LANG')
}

class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.timeout = 10
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)

http = requests.Session()
adapter = TimeoutHTTPAdapter(
    timeout = 10,
    max_retries = Retry(
        total = 3,
        backoff_factor = 0.1,
        status_forcelist = [500, 502, 503, 504]
    )
)

# mount the adapter to schemes
http.mount('http://', adapter)
http.mount('https://', adapter)
ht.client.HTTPConnection.debuglevel = 1 if DEBUG else 0

# the language code
lang = locale.getdefaultlocale()[0].split('_')[0] # eg: de, en, es, ...

# translation function
def t(string, lang = lang, **kwargs):
    if lang in messages and string in messages[lang] and messages[lang][string] != '':
        string = messages[lang][string]
    elif LANGUAGE_TRANSLATION:
        print(f'\033[0;31m--> Missing translaton for language\033[0m "{lang}": "{string}"', file = sys.stderr)
        if not hasattr(t, 'messages'): t.messages = {}
        if not lang in t.messages: t.messages[lang] = {}
        t.messages[lang][string] = ''

    try:
        string = string.format(**kwargs)
    except KeyError:
        pass
    return string

# Obtains a variable in key=value-format from a file
# @param string variable the name of the variable
# @param string file filename
# @return string the value or the empty string
def getVariableFromFile(variable, file):
    with open(file, "r") as fh:
        for line in fh:
            try:
                key, value = line.split("=", 1)
                if key == variable:
                    return value.strip('"\'\n ')
            except: pass            
    return ''

# Obtains all variables in key=value-format from a file
def getVariablesFromFile(file, r = {}):
    with open(file, "r") as fh:
        for line in fh:
            try:
                key, value = line.split("=", 1)
                if key != '':
                    r[key.strip('"\'\n ')] = value.strip('"\'\n ')
            except: pass
    return r

def isDeb9OrNewer():
    v = int(getVariableFromFile('VERSION_ID', '/etc/os-release'))
    return not (v != '' and v <= 8)

# @param string ver version string to compare
# @param string wants compare ver with this (eg: <=1.2.3)
def check_version(ver, wants, exit_text = None):
    r = re.search('([\>,\<,\=]+)([0-9,\.]+)', wants)
    p = lambda v: version.parse(v)
    if r:
        operator = r.group(1)
        ver2 = r.group(2)
    else:
        operator = '=='
        ver2 = wants

    ver = p(ver)
    ver2 = p(ver2)

    ret = (
        (operator == '==' and ver == ver2)
        or (operator == '<=' and ver <= ver2)
        or (operator == '>=' and ver >= ver2)
        or (operator == '<'  and ver <  ver2)
        or (operator == '>'  and ver >  ver2)
        or False
    )

    if ret == False and exit_text is not None:
        exit_with_error_message(exit_text.format(ver = ver, wants = wants))

    return ret

# Handles any cleanup
def clean_exit(reason = None):
    print('Exiting gracefully (reason: {0})'.format(reason), file = sys.stderr)

    # revert all changes to iptables
    helpers.run('iptables-save | grep -v "searchExamServer" | iptables-restore -w')
    helpers.run('iptables-legacy-save | grep -v "searchExamServer" | iptables-legacy-restore -w')

    # remove the glados entries in firewall whitelist
    line = '^{gladosProto}://{gladosHost}'.format(**glados)
    line = line.replace(".", "\.") if isDeb9OrNewer() else line
    remove_line_from_file(urlWhitelistFile, line)

    helpers.run('umount /run/initramfs/newroot 2>/dev/null')
    helpers.run('umount -l /run/initramfs/{base,exam} 2>/dev/null')

    if isDeb9OrNewer(): helpers.run('squid -k reconfigure') # iptables stays

    if LANGUAGE_TRANSLATION and hasattr(t, 'messages'):
        print("Missing translatons summary:\n"+"#"*40+"\n", json.dumps(t.messages, indent = 4), "\n"+"#"*40)

    exit(0)

def trap(signal_received, frame):
    clean_exit('signal {0} recieved'.format(signal_received))

def file_get_contents(file):
    with open(file) as f:
        return f.read()

def file_put_contents(file, contents, append = False):
    with open(file, 'a' if append else 'w') as f:
        return f.write(contents)

def remove_line_from_file(file, line):
    with open(file, "r") as f: lines = f.readlines()
    with open(file, "w") as f:
        for l in lines:
            if l.strip("\n") != line:
                f.write(l)

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

# Accepts all flags that zenity accepts as keyword arguments
def zenity(**kwargs):
    cmd = 'zenity'
    for key, value in kwargs.items():
        if isinstance(value, bool) and value:
            cmd += f' --{key}'
        elif isinstance(value, int):
            cmd += f' --{key}={value}'
        elif isinstance(value, str):
            cmd += f' --{key}={shlex.quote(value)}'
    return helpers.run(cmd, env = env)

def exit_with_error_message(mesg, **kwargs):
    if DEBUG: print(mesg, file=sys.stderr)
    default_args = {
        'title': t('Error'),
        'error': True,
        'width': 300,
        'text': mesg
    }
    kwargs = {**default_args, **kwargs} # merge the args, where the second has priority
    zenity(**kwargs)
    clean_exit(mesg)   

def http_get(url, **kwargs):
    if DEBUG: print(f"getting URL: {url}")
    try:
        r = http.get(url, **kwargs)
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        if DEBUG: print(repr(e), file = sys.stderr)
        r = requests.models.Response()
        r.status_code = -1
        r.code = str(e)
        r.error_type = repr(e)
    return r

def get_lernstick_version():
    lernstick_version_files = [
        '/usr/local/lernstick.html',
        '/run/live/rootfs/filesystem.squashfs/usr/local/lernstick.html'
    ]
    for file in lernstick_version_files:
        try:
            with open(file) as f:
                for line in f.readlines():
                    res = re.search('([0-9,\-]{8,})', line)
                    if res:
                        return res.group(1).replace('-', '')
        except: pass

    exit_with_error_message(t('Cannot obtain current Lernstick version.'))

def get_lernstick_flavor():
    theme = '/run/live/medium/boot/grub/themes/lernstick/theme.txt'
    backup = '/usr/bin/lernstick_backup'
    if os.path.isfile(theme) and os.access(theme, os.R_OK):
        return 'exam' if re.search('title-text.*Prüfung') else 'standard'
    else:
        return 'exam' if os.path.exists(backup) else 'standard'

# get client information
def get_client_version():
    try:
        with open(compatFile) as f:
            client_compat = json.load(f)
    except:
        exit_with_error_message(t("Cannot open compatibility file {path}", path = compatFile))

    client_compat['lernstick_version'] = get_lernstick_version()
    client_compat['lernstick_flavor'] = get_lernstick_flavor()
    return client_compat

# get server information
def get_server_version():
    r = http_get(glados['actionInfo'])
    if r.status_code != 200:
        exit_with_error_message(t("Unable to fetch Glados server version information."))

    return r.json()

def get_ssh_key():
    r = http_get(glados['actionSSHKey'])
    if r.status_code != 200:
        exit_with_error_message(t("Failed to fetch the SSH key from Glados server."))

    return r.content.decode("utf-8") 

# unique all lines in file
def unique_lines(file):
    with open(file) as f:
        lines = f.readlines()
        file_put_contents(file, ''.join(set(lines)))

def zenity_send(p, mesg):
    p.stdin.write("#{0}\n".format(mesg).encode('utf-8'))
    p.stdin.flush()

#if LANGUAGE_TRANSLATION: t.messages = {}
if __name__ == '__main__':

    # Exit if already running
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('localhost', 18493))
    except OSError:
        print('Program is already running, exitting.', file = sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGINT, trap)
    signal.signal(signal.SIGTERM, trap)

    # allow bonjour/zeroconf
    helpers.run('iptables -I INPUT -p udp --dport 5353 -d 224.0.0.251 -m comment --comment "searchExamServer" -j ACCEPT')
    helpers.run('iptables -I OUTPUT -p udp --dport 5353 -d 224.0.0.251 -m comment --comment "searchExamServer" -j ACCEPT')

    # create the directory structure and cleanup
    for path in ['newroot','base','exam','tmpfs','squashfs','backup/home/user']:
        os.makedirs('/run/initramfs/' + path, exist_ok = True)
    os.chown('/run/initramfs/backup/home/user', 1000, 1000) # @todo evtl. shutil.chown() accepts names
    if os.path.exists(retoreStateFile): os.remove(retoreStateFile)

    if os.path.isfile(infoFile) and os.access(infoFile, os.R_OK):
        glados = getVariablesFromFile(infoFile)
        if DEBUG: print("Using Glados information from previous run (file {0}):\n".format(infoFile), json.dumps(glados, indent = 4))

    # if a configfile is used, don't display a selection list and use the config values instead
    if os.path.isfile(configFile) and os.access(configFile, os.R_OK):
        fixed = True

        # starting subprocess
        cmd = 'zenity --width=300 --progress --pulsate --no-cancel --title="{title}" --text="{text}" --auto-close'.format(
            title = t('Search'),
            text = t('Taking Glados server from configuration file.'),
        )
        zenity_process = subprocess.Popen(cmd, env = env, shell = True, stdin = subprocess.PIPE)

        if DEBUG: print("Configfile found, using {}.".format(configFile))

        glados = getVariablesFromFile(configFile, glados)

        for var in variables:
            if not var in glados or glados[var] == '':
                exit_with_error_message(t("Variable {var} not given in configuration file {file}. Please add this variable to the configuration file.",
                    var = var,
                    file = configFile
                ))

        for action in actions:
            glados[f"action{action}"] = "{gladosProto}://{gladosHost}:{gladosPort}/{0}".format(glados[f"action{action}"], **glados)

        retval, glados['interface'] = helpers.run("ip -s route get {gladosIp} | perl -ne 'print $1 if /dev[\s]+([^\s]+)/'".format(**glados))

        if DEBUG: print("Using Glados information from config file {0}:\n".format(configFile), json.dumps(glados, indent = 4))

        if retval == False:
            exit_with_error_message(t("The Glados server ({gladosDesc}, {gladosHost}, {gladosIp}) configured in the configuration file {file} is not reachable via your network connection(s). Aborting.", file = configFile, **glados), width = 500)

        # ending subprocess
        # dont end here, end there https://github.com/Lernstick/lernstick-exam-client/blob/master/usr/bin/searchExamServer#L312
        #stdout = zenity_process.communicate(input = b'100')[0] # 

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
                title = t('Searching for exam server.'),
                text = t('The following list of exam servers was found in the network. Please select the one you want to use.'),
                name = t('Name'),
                ip = t('IP'),
                host = t('Host'),
                port = t('Port'),
                protocol = t('Protocol'),
                interface = t('Interface')
            )

            zenity_process = subprocess.Popen(zenity_cmd,
                env = env,
                shell = True,
                stdin = subprocess.PIPE,
                stdout = subprocess.PIPE
            )
            avahi_process = subprocess.Popen('avahi-browse -rp --no-db-lookup -a',
                env = env,
                shell = True,
                stdin = subprocess.PIPE,
                stdout = subprocess.PIPE,
                bufsize = 1 # line buffered
            )

            readline = enqueue_process(avahi_process) # "improved" readline that can take a timeout argument

            n = 1
            entries = {}
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

                            entries[n] = {}
                            entries[n]['gladosDesc'] = decimals_to_hex(pieces[3])
                            entries[n]['gladosIp'] = pieces[7]
                            entries[n]['gladosHost'] = pieces[6]
                            entries[n]['gladosPort'] = int(pieces[8])
                            entries[n]['gladosProto'] = 'https' if pieces[4] == '_https._tcp' else 'http'
                            entries[n]['interface'] = pieces[1]

                            # parse the action URLs and skip if we miss some
                            for action in actions:
                                res = re.search(f"action{action}='([^\']+)'", pieces[9])
                                if res:
                                    entries[n][f"action{action}"] = "{gladosProto}://{gladosHost}:{gladosPort}/{0}".format(res.group(1), **entries[n])
                                else:
                                    if DEBUG: print("Skipping invalid Glados DNS-entry for {gladosIp}:{gladosPort}".format(**entries[n]))
                                    continue

                            # get the info URL manually
                            entries[n]["actionInfo"] = entries[n]["actionSSHKey"].replace('/ticket/ssh-key', '/config/info')

                            output_line = '{0}\n{gladosDesc}\n{gladosIp}\n{gladosHost}\n{gladosPort}\n{gladosProto}\n{interface}\n'.format(n, **entries[n])

                            if DEBUG: print("Found Glados server #{0} via DNS: {gladosDesc}, {gladosHost}, {gladosIp}, {gladosPort}".format(n, **entries[n]))
                            output_line = decimals_to_hex(output_line)
                            zenity_process.stdin.write(str.encode(output_line))
                            zenity_process.stdin.flush()
                            n += 1

            zenity_output = zenity_process.communicate()[0].rstrip().decode("utf-8")
            choice = int(zenity_output) if zenity_output != '' else False

        if choice in entries:
            glados = {**glados, **entries[choice]} # merge the args, where the second has priority
            if DEBUG: print("User selected Glados server #{0}".format(choice))
            if DEBUG: print("Using Glados information obtained from DNS entry #{0}:\n".format(choice), json.dumps(glados, indent = 4))
        else:
            exit_with_error_message(t('Choice is invalid.'))

    if (not 'gladosHost' in glados) or (not 'gladosPort' in glados):
        exit_with_error_message(t('Glados host not found.'))


    # append the hostname and IP of glados to the /etc/hosts file, such that in the exam,
    # the server IP can be resolved without having a proper DNS service in the network.
    shutil.copy('/etc/hosts', '/var/lib/lernstick-exam-client/persistent/etc/hosts')
    file_put_contents('/var/lib/lernstick-exam-client/persistent/etc/hosts',
        f"{glados['gladosIp']}     {glados['gladosHost']}\n", append = True)

    if DEBUG: print("Exam server found.")

    if fixed:
        # finish the processes
        stdout = zenity_process.communicate(input = b'100')[0]
        zenity_process.stdin.close()
        zenity_process.terminate()

        # Ask the user to proceed
        if not zenity(
                question = True,
                width = 400,
                title = t("Continue"),
                text = t("An exam server was found in the configuration file (via {interface}):\n\n    Desciption: {gladosDesc}\n    Hostname: {gladosHost}\n    IP: {gladosIp}\n\nSwitch to exam mode?", **glados)
        )[0]:
            clean_exit("User aborted before switching to exam mode.")
    else:
        zenity_process.stdin.close()
        zenity_process.terminate()
        avahi_process.stdin.close()
        avahi_process.terminate()

    # starting new zenity subprocess
    cmd = 'zenity --width=300 --progress --pulsate --no-cancel --title="{title}" --text="{text}" --auto-close'.format(
        title = t('Please wait'),
        text = t('Connecting to server.'),
    )
    zenity_process = subprocess.Popen(cmd, env = env, shell = True, stdin = subprocess.PIPE)

    zenity_send(zenity_process, t('Configuring firewall'))

    # configuring firewall
    line = '^{gladosProto}://{gladosHost}\n'.format(**glados)
    if isDeb9OrNewer(): line = line.replace(".", "\.")
    file_put_contents(urlWhitelistFile, line, append = True)

    unique_lines(urlWhitelistFile)

    helpers.run('service lernstick-firewall restart')
    if isDeb9OrNewer(): helpers.run('squid -k reconfigure')
    helpers.run('iptables -I INPUT -p tcp --dport 22 -s {gladosIp} -m comment --comment "searchExamServer" -j ACCEPT'.format(**glados))
    helpers.run('iptables -I OUTPUT -p tcp --dport {gladosPort} -d {gladosIp} -m comment --comment "searchExamServer" -j ACCEPT'.format(**glados))

    # this sleep is needed, else the http request would fail (network error)
    time.sleep(1)

    zenity_send(zenity_process, t('Fetching SSH key'))
    glados['sshKey'] = get_ssh_key()

    client = get_client_version()

    zenity_send(zenity_process, t('Fetching server information'))
    server = get_server_version()

    zenity_send(zenity_process, t('Checking versions'))

    if DEBUG:
        print("Version check")
        print("Client version information:\n", json.dumps(client, indent = 4))
        print("Server version information:\n", json.dumps(server, indent = 4))

    check_version(server['server_version'], client['wants_server_version'],
        t("Server version mismatch. Got {ver}, but client needs {wants}."))
    check_version(client['lernstick_flavor'], server['wants_lernstick_flavor'],
        t("Client version mismatch. Got {ver}, but server needs {wants}."))
    check_version(client['lernstick_version'], server['wants_lernstick_version'],
        t("Client version mismatch. Got {ver}, but server needs {wants}."))
    check_version(client['client_version'], server['wants_client_version'],
        t("Client version mismatch. Got {ver}, but server needs {wants}."))

    if DEBUG: print("Version check was successful!")

    zenity_send(zenity_process, t('Setting up token request'))

    # create environment
    os.makedirs('/root/.ssh', mode = 700, exist_ok = True)
    file_put_contents('/root/.ssh/authorized_keys', glados['sshKey'], append = True)

    # The or fixes the newest debian9 version
    _, glados['partitionSystem'] = helpers.run("blkid -l -L system || echo /dev/sr0")

    # write the info file
    contents = ''
    for variable in variables + ['partitionSystem']:
        contents += '{0}="{1}"\n'.format(variable, glados[variable])
    file_put_contents(infoFile, contents)

    # remount /run without noexec (Debian 9 changed this, /run/initramfs/shutdown will not be executed elsewhere)
    helpers.run("mount -n -o remount,exec /run")

    url = glados['actionDownload'].format(token = glados['token'] if 'token' in glados else '')

    # finish the zenity processes
    stdout = zenity_process.communicate(input = b'100')[0]
    zenity_process.stdin.close()
    zenity_process.terminate()

    # finally open wxbrowser
    if DEBUG: print("Opening URL {0} in wxbrowser".format(url))
    cmd = 'sudo -u user /usr/bin/wxbrowser --geometry "800x310" -c -n "{title}" -i "/usr/share/icons/oxygen/base/128x128/actions/system-search.png" "{url}"'.format(
        title = t("Exam Client"),
        url = url
    )
    helpers.run(cmd, env = env)

    clean_exit('Reached end.')
