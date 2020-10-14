#!/bin/bash

infoFile="/info"
configFile="/config.json"
python="/usr/bin/python"
DEBUG=true

[ -r "${infoFile}" ] && . ${infoFile}

function config_value()
{
  if [ -n "${config}" ]; then
    config="$(cat "${configFile}")"
  fi

  v="$(echo "${config}" | ${python} -c 'import sys, json; print json.load(sys.stdin)["config"]["'${1}'"]')"
  $DEBUG && >&2 echo "${1} is set to ${v}"
  echo "$v"
}
