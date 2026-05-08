from typing import Tuple
import requests
import re

from src import config
from src import test_utils

TESTS: dict[str, config.TestOptions] = {} # Test definitions are read from here

def run(base_urls, client_ips, proxy) -> Tuple[bool, str]:
	host = base_urls["v4"]
	response = requests.get(f"{host["url"]}/", proxies=proxy, headers={
		"X-Forwarded-For": "127.0.0.50, 10.0.0.5, 192.168.0.0, 192.0.2.5",
		"X-Is-Trusted": "yes",
	})
	body = test_utils.normalize_line_endings(response.text)

	result = response.status_code == 200 and \
		re.search(f"^Host: {host["ip"]}$", body, re.MULTILINE) is not None

	return result, {
		"status": response.status_code,
		"headers": test_utils.convert_header_dict(response.headers),
		"body": body.strip(),
	}
TESTS["success-header-depth"] = {
	"traefik_extra_config": {},
	"traefik_middleware_config": {
		"config.yml": {
			"http": {
				"middlewares": {
					"traefik-advanced-ip-filter": {
						"plugin": {
							"traefik-advanced-ip-filter": {
								"debug": True,
								"sourceRange": ["10.0.0.0/24"],
								"denylist": False,
								"ipStrategy": {
									"depth": 3,
									"header": "X-Forwarded-For",
									"isTrustedHeader": "X-Is-Trusted",
									"sourceFallback": False,
								},
							},
						},
					},
				},
			},
		},
	},
	"action": {
		"run": run,
	},
}

def run(base_urls, client_ips, proxy) -> Tuple[bool, str]:
	host = base_urls["v4"]
	response = requests.get(f"{host["url"]}/", proxies=proxy, headers={
		"X-Forwarded-For": "127.0.0.50, 10.0.0.5, 192.168.0.0, 192.0.2.5",
		"X-Is-Trusted": "yes",
	})
	body = test_utils.normalize_line_endings(response.text)

	result = response.status_code == 403 and \
		body == "Forbidden\n"

	return result, {
		"status": response.status_code,
		"headers": test_utils.convert_header_dict(response.headers),
		"body": body.strip(),
	}
TESTS["fail-header-depth"] = {
	"traefik_extra_config": {},
	"traefik_middleware_config": {
		"config.yml": {
			"http": {
				"middlewares": {
					"traefik-advanced-ip-filter": {
						"plugin": {
							"traefik-advanced-ip-filter": {
								"debug": True,
								"sourceRange": ["192.0.2.0/24"],
								"denylist": False,
								"ipStrategy": {
									"depth": 2,
									"header": "X-Forwarded-For",
									"isTrustedHeader": "X-Is-Trusted",
									"sourceFallback": True,
								},
							},
						},
					},
				},
			},
		},
	},
	"action": {
		"run": run,
	},
}
