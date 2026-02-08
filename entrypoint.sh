#!/bin/bash
set -e

if [ -f /data/options.json ]; then
    # Home Assistant add-on mode: generate config from HA options
    python3 -c "
import json
import yaml

with open('/data/options.json') as f:
    opts = json.load(f)

config = {
    'server': {'host': '0.0.0.0', 'port': 80},
    'frontend': {
        'type': 'shelly',
        'shelly': {
            'phases': opts.get('shelly_phases', 1),
            'mdns': opts.get('shelly_mdns', True),
        },
    },
    'backend': {
        'type': 'envoy',
        'envoy': {
            'host': opts['envoy_host'],
            'token': opts['envoy_token'],
            'poll_interval': opts.get('envoy_poll_interval', 2.0),
            'verify_ssl': opts.get('envoy_verify_ssl', False),
        },
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
