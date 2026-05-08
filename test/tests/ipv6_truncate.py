from typing import Tuple
import requests
import re

from src import config
from src import test_utils

TESTS: dict[str, config.TestOptions] = {} # Test definitions are read from here

def run(base_urls, client_ips, proxy) -> Tuple[bool, str]:
	host = base_urls["v6"]
	response = requests.get(f"{host["url"]}/", proxies=proxy, headers={})
	body = test_utils.normalize_line_endings(response.text)

	result = response.status_code == 200 and \
		re.search(f"^Host: \\[{host["ip"]}\\]$", body, re.MULTILINE) is not None and \
		re.search(f"^X-Real-Ip: {client_ips["v6"]}$", body, re.MULTILINE) is not None

	return result, {
		"status": response.status_code,
		"headers": test_utils.convert_header_dict(response.headers),
		"body": body.strip(),
	}
TESTS["success-ipv6-no-truncate"] = {
	"traefik_extra_config": {},
	"traefik_middleware_config": {
		"config.yml": {
			"http": {
				"middlewares": {
					"traefik-advanced-ip-filter": {
						"plugin": {
							"traefik-advanced-ip-filter": {
								"debug": True,
								"sourceRange": ["cfff:d518:1358:3724:1e59:ddd8:9586:1acd"],
								"ipStrategy": {
									"header": "",
									"isTrustedHeader": "",
									"ipv6Subnet": 128
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
	host = base_urls["v6"]
	response = requests.get(f"{host["url"]}/", proxies=proxy, headers={})
	body = test_utils.normalize_line_endings(response.text)

	result = response.status_code == 200 and \
		re.search(f"^Host: \\[{host["ip"]}\\]$", body, re.MULTILINE) is not None and \
		re.search(f"^X-Real-Ip: {client_ips["v6"]}$", body, re.MULTILINE) is not None

	return result, {
		"status": response.status_code,
		"headers": test_utils.convert_header_dict(response.headers),
		"body": body.strip(),
	}
TESTS["success-ipv6-truncate"] = {
	"traefik_extra_config": {},
	"traefik_middleware_config": {
		"config.yml": {
			"http": {
				"middlewares": {
					"traefik-advanced-ip-filter": {
						"plugin": {
							"traefik-advanced-ip-filter": {
								"debug": True,
								"sourceRange": ["cfff:d518:1358:3724:1e59:ddd8::"],
								"ipStrategy": {
									"header": "",
									"isTrustedHeader": "",
									"ipv6Subnet": 96
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
	host = base_urls["v6"]
	response = requests.get(f"{host["url"]}/", proxies=proxy, headers={})
	body = test_utils.normalize_line_endings(response.text)

	result = response.status_code == 403 and \
		body == "Forbidden\n"

	return result, {
		"status": response.status_code,
		"headers": test_utils.convert_header_dict(response.headers),
		"body": body.strip(),
	}
TESTS["fail-ipv6-no-truncate"] = {
	"traefik_extra_config": {},
	"traefik_middleware_config": {
		"config.yml": {
			"http": {
				"middlewares": {
					"traefik-advanced-ip-filter": {
						"plugin": {
							"traefik-advanced-ip-filter": {
								"debug": True,
								"sourceRange": ["cfff:d518:1358:3724:1e59:ddd8::"],
								"ipStrategy": {
									"header": "",
									"isTrustedHeader": "",
									"ipv6Subnet": 128
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
	host = base_urls["v6"]
	response = requests.get(f"{host["url"]}/", proxies=proxy, headers={})
	body = test_utils.normalize_line_endings(response.text)

	result = response.status_code == 403 and \
		body == "Forbidden\n"

	return result, {
		"status": response.status_code,
		"headers": test_utils.convert_header_dict(response.headers),
		"body": body.strip(),
	}
TESTS["fail-ipv6-truncate"] = {
	"traefik_extra_config": {},
	"traefik_middleware_config": {
		"config.yml": {
			"http": {
				"middlewares": {
					"traefik-advanced-ip-filter": {
						"plugin": {
							"traefik-advanced-ip-filter": {
								"debug": True,
								"sourceRange": ["cfff:d518:1358:3724:1e59:ddd8:9586:1acd"],
								"ipStrategy": {
									"header": "",
									"isTrustedHeader": "",
									"ipv6Subnet": 96
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
