import sys # sys.stdout.encoding, sys.stdin
import os # os.path.isfile()
import glob # glob.glob()
import subprocess # subprocess.check_output(), subprocess.call()
import json # json.load
import re # re.compile(), re.match()
import shlex # quote() strings for shell command
import logging # logging.Formatter

logger = logging.getLogger('root')

"""
Class for the colored output of logging
"""
class TerminalColorFormatter(logging.Formatter):
    grey = "\x1b[90;20m"
    default = "\x1b[39;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s - %(message).400s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + fmt + reset,
        logging.INFO: default + fmt + reset,
        logging.WARNING: yellow + fmt + reset,
        logging.ERROR: red + fmt + reset,
        logging.CRITICAL: bold_red + fmt + reset
    }

    def format(self, record):
        return logging.Formatter(self.FORMATS.get(record.levelno)).format(record)

"""
Class for the file logging
"""
class FileFormatter(logging.Formatter):
    fmt = "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"

    def format(self, record):
        return logging.Formatter(self.fmt).format(record)

"""
Return a exam config item

@param string variable variable to get
@param mixed the default value if the config value is not set
@param string file the config file
@return mixed the variable or the value of default if not found
"""
def get_config(variable, default = None, file = '/config.json'):
    with open(file) as json_file:
        data = json.load(json_file)
        try:
            value = data["config"][variable]
        except:
            value = default
    return value

"""
Return a variable from the info file.

@param string variable variable to get
@param string file the info file
@return string|None the variable or None if not found
"""
def get_info(variable, file = '/info'):
    cmd = 'set -a; source "{file}"; set +a; printf "%s" "${variable}"'.format(
        file = file,
        variable = variable)
    string = subprocess.check_output(['bash', '-c', cmd]).decode(sys.stdout.encoding)
    return string if string != "" else None

"""
Return an environment variable from a currently running process.

@param string variable environment variable to retrieve
@param string pid process id of the process to retrieve the environment variable from
@param string uid check only processes with user id
@param string filter regex to filter the variable value by (first item that matches is returned)
@return string|False the variable or False if not found
"""
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

"""
Runs a command an returns its output as well as its return value

@param string cmd the command (can contain pipes)
@param dict env the environment variables
@param string encoding the output encoding
@see https://docs.python.org/3/library/codecs.html#standard-encodings
@return bool, string the return value and the command output
"""
def run(cmd, env = {}, encoding = 'utf-8'):
    binary = os.path.basename(cmd.split()[0])
    logger.debug(f"running command: {cmd}")
    process = subprocess.Popen(['bash', '-c', cmd],
        env = env,
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE
    )
    try:
        output, error = process.communicate()
    except KeyboardInterrupt:
        logger.error("command failed");
        output, error = (b"", b"")

    ret = True if process.returncode == 0 else False
    output = output if encoding == None else output.decode(encoding).strip()
    error = error if encoding == None else error.decode(encoding).strip()
    l = logger.debug if ret else logger.error
    l(f"{binary} - exit code: {process.returncode}")
    l(f"{binary} - command stdout:{output if output else None}")
    l(f"{binary} - command stderr:{error if error else None}")
    return ret, output if ret else output + error

"""
Equivalent to PHPs file_put_contents function

@param file: path to file
@param contents: string to write to file
@param append: whether to append or overwrite (default)
@return bool: fail/success
"""
def file_put_contents(file, contents, append = False):
    with open(file, 'a' if append else 'w') as f:
        return f.write(contents)

"""
Uniques all lines in file

@param file: path to file
"""
def unique_lines(file):
    with open(file) as f:
        lines = f.readlines()
        file_put_contents(file, ''.join(set(lines)))

        
"""
Construct a zenity command

@param: Accepts all flags that zenity accepts as keyword arguments
@return string: the generated zenity command
"""
def zenity(**kwargs):
    cmd = 'zenity'
    for key, value in kwargs.items():
        key = key.replace('_', '-')
        if isinstance(value, bool) and value:
            cmd += f' --{key}'
        elif isinstance(value, int):
            cmd += f' --{key}={value}'
        elif isinstance(value, str):
            cmd += f' --{key}={shlex.quote(value)}'
        elif isinstance(value, list):
            for v in value: cmd += f' --{key}={shlex.quote(v)}'
    return cmd
