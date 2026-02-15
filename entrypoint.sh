#!/bin/bash
set -e

if [ -f /data/options.json ]; then
    # Home Assistant add-on mode: generate config from HA options
    python3 -c "
import json
import yaml

with open('/data/options.json') as f:
    opts = json.load(f)

envoy_config = {
    'host': opts['envoy_host'],
    'poll_interval': opts.get('envoy_poll_interval', 2.0),
    'verify_ssl': opts.get('envoy_verify_ssl', False),
}

# Token is optional when credentials are provided
token = opts.get('envoy_token')
if token:
    envoy_config['token'] = token

# Enlighten Cloud credentials for automatic token refresh
for key in ('username', 'password', 'serial'):
    val = opts.get(f'envoy_{key}')
    if val:
        envoy_config[key] = val

config = {
    'server': {'host': '0.0.0.0', 'port': 80},
    'frontend': {
        'type': opts.get('frontend_type', 'shelly'),
        'shelly': {
            'phases': int(opts.get('shelly_phases', 1)),
            'mdns': opts.get('shelly_mdns', True),
        },
    },
    'backend': {
        'type': opts.get('backend_type', 'envoy'),
        'envoy': envoy_config,
    },
}

mac = opts.get('shelly_mac')
if mac:
    config['frontend']['shelly']['mac'] = mac

with open('/data/config.yaml', 'w') as f:
    yaml.dump(config, f, default_flow_style=False)
"
    exec meter-emulator -c /data/config.yaml
else
    exec "$@"
fi
