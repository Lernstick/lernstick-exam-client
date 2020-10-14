#!/bin/bash

infoFile="/info"
configFile="/config.json"
DEBUG=true

[ -r "${infoFile}" ] && . ${infoFile}

function config_value()
{
  config="$(cat "${configFile}")"
  v="$(cat "${configFile}" | python2 -c 'import sys, json; print json.load(sys.stdin)["config"]["'${1}'"]')"
  $DEBUG && >&2 echo "${1} is set to ${v}"
  echo "$v"
}

