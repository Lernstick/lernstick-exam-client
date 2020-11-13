import sys # sys.stdout.encoding, sys.stdin
import os # os.path.isfile()
import glob # glob.glob()
import subprocess # subprocess.check_output(), subprocess.call()
import json # json.load

##
# Return a exam config item
# @param string variable variable to get
# @param mixed the default value if the config value is not set
# @param string file the config file
# @return mixed the variable or the value of default if not found
##
def get_config (variable, default = None, file = '/config.json'):
    with open(file) as json_file:
        data = json.load(json_file)
        try:
            value = data["config"][variable]
        except:
            value = default
    return value

##
# Return a variable from the info file.
# @param string variable variable to get
# @param string file the info file
# @return string|None the variable or None if not found
##
def get_info (variable, file = '/info'):
    cmd = 'set -a; source "{file}"; set +a; printf "%s" "${variable}"'.format(
        file = file,
        variable = variable)
    string = subprocess.check_output(['bash', '-c', cmd]).decode(sys.stdout.encoding)
    return string if string != "" else None

##
# Return an environment variable from a currently running process.
# @param string variable environment variable to retrieve
# @param string pid process id of the process to retrieve the environment variable from
# @return string|False the variable or False if not found
##
def get_env (variable, pid = "*"):
    for file in glob.glob("/proc/{0}/environ".format(pid)):
        if os.path.isfile(file):
            handle = open(file, 'r')
            for line in handle.read().split('\0'):
                try:
                    var, value = line.split("=", 2)
                    if (var == variable):
                        return value
                    print("{} = {}".format(var, val))
                except: pass
    return None

##
# Runs a command an returns its output as well as its return value
# @param string cmd the command (can contain pipes)
# @param dict env the environment variables
# @param string encoding the output encoding
# @see https://docs.python.org/3/library/codecs.html#standard-encodings
# @return bool, string the return value and the command output
##
def run (cmd, env = {}, encoding = 'utf-8'):
    process = subprocess.Popen(['bash', '-c', cmd],
        env = env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    output, error = process.communicate()
    ret = True if process.returncode == 0 else False
    output = output if encoding == None else output.decode(encoding).strip()
    return ret, output

