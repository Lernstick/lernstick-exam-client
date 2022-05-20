import sys # sys.stdout.encoding, sys.stdin
import os # os.path.isfile()
import glob # glob.glob()
import subprocess # subprocess.check_output(), subprocess.call()
import json # json.load
import re # re.compile(), re.match()
import logging # logging.Formatter

logger = logging.getLogger('root')

##
# Class for the colored output of logging
##
class TerminalColorFormatter(logging.Formatter):
    grey = "\x1b[90;20m"
    default = "\x1b[39;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + fmt + reset,
        logging.INFO: default + fmt + reset,
        logging.WARNING: yellow + fmt + reset,
        logging.ERROR: red + fmt + reset,
        logging.CRITICAL: bold_red + fmt + reset
    }

    def format(self, record):
        formatter = logging.Formatter(self.FORMATS.get(record.levelno))
        return logging.Formatter(self.FORMATS.get(record.levelno)).format(record)

##
# Return a exam config item
# @param string variable variable to get
# @param mixed the default value if the config value is not set
# @param string file the config file
# @return mixed the variable or the value of default if not found
##
def get_config(variable, default = None, file = '/config.json'):
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
def get_info(variable, file = '/info'):
    cmd = 'set -a; source "{file}"; set +a; printf "%s" "${variable}"'.format(
        file = file,
        variable = variable)
    string = subprocess.check_output(['bash', '-c', cmd]).decode(sys.stdout.encoding)
    return string if string != "" else None

##
# Return an environment variable from a currently running process.
# @param string variable environment variable to retrieve
# @param string pid process id of the process to retrieve the environment variable from
# @param string uid check only processes with user id
# @param string filter regex to filter the variable value by (first item that matches is returned)
# @return string|False the variable or False if not found
##
def get_env(variable, pid = '*', uid = '*', filter = r'.*'):
    r = re.compile(filter)
    for file in glob.glob('/proc/{0}/environ'.format(pid)):
        if os.path.isfile(file) and (uid == '*' or os.stat(file).st_uid == uid):
            handle = open(file, 'r')
            for line in handle.read().split('\0'):
                try:
                    var, value = line.split('=', 2)
                    if (var == variable and re.match(r, value)):
                        return value
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
def run(cmd, env = {}, encoding = 'utf-8'):
    logger.debug(f"running command: {cmd}")
    process = subprocess.Popen(['bash', '-c', cmd],
        env = env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    output, error = process.communicate()
    ret = True if process.returncode == 0 else False
    output = output if encoding == None else output.decode(encoding).strip()
    error = error if encoding == None else error.decode(encoding).strip()
    l = logger.debug if ret else logger.error
    l(f"exit code: {process.returncode}")
    l(f"command stdout:{output if output else None}")
    l(f"command stderr:{error if error else None}")
    return ret, output if ret else output + error
