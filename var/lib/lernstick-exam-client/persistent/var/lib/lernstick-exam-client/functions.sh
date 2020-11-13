#!/bin/bash

infoFile="/info"
configFile="/config.json"
DEBUG=true
python="python2"

[ -r "${infoFile}" ] && . ${infoFile}

# Echo the configuration value from the config json
# @param $1 the config value to return
# @param $2 the default value if the config value is not set
function config_value()
{
  v="$(cat "${configFile}" | ${python} -c 'import sys, json; print json.load(sys.stdin)["config"]["'${1}'"]' 2>/dev/null)"
  retval=$?
  if [ ${retval} -ne 0 ]; then
    $DEBUG && >&2 echo "${1} not found in config file"
    echo "${2}" #return default value
  else
    $DEBUG && >&2 echo "${1} is set to ${v}"
    echo "$v"
  fi
}
