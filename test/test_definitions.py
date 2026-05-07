from src import config

TESTS: dict[str, config.TestOptions] = {
	"success-no-header": {
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
										"depth": 0,
										"header": "",
										"sourceFallback": True,
									},
								},
							},
						},
					},
				},
			},
		},
		"request_headers": {},
		"conditions": [
			{
				"type": "regex",
				"match": r"^RemoteAddr: 192.0.2.128:\d+\r?$",
				"negate": False,
			},
			{
				"type": "regex",
				"match": r"^Host: traefik\r?$",
				"negate": False,
			},
		],
	},
	"success-header": {
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
										"depth": 1,
										"header": "X-Custom-Forward-Header",
										"isTrustedHeader": "X-Custom-Trusted-Header",
										"sourceFallback": False,
									},
								},
							},
						},
					},
				},
			},
		},
		"request_headers": {
			"X-Custom-Forward-Header": "10.0.0.5",
			"X-Custom-Trusted-Header": "true",
		},
		"conditions": [
			{
				"type": "regex",
				"match": r"^RemoteAddr: 192.0.2.128:\d+\r?$",
				"negate": False,
			},
			{
				"type": "regex",
				"match": r"^Host: traefik\r?$",
				"negate": False,
			},
		],
	},
	"success-header-depth": {
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
		"request_headers": {
			"X-Forwarded-For": "127.0.0.50, 10.0.0.5, 192.168.0.0, 192.0.2.5",
			"X-Is-Trusted": "yes",
		},
		"conditions": [
			{
				"type": "regex",
				"match": r"^RemoteAddr: 192.0.2.128:\d+\r?$",
				"negate": False,
			},
			{
				"type": "regex",
				"match": r"^Host: traefik\r?$",
				"negate": False,
			},
		],
	},
	"success-header-excluded-ips": {
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
										"excludedIPs": ["192.168.0.0", "192.0.2.5", "127.0.0.50"],
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
		"request_headers": {
			"X-Forwarded-For": "127.0.0.50, 10.0.0.5, 192.168.0.0, 192.0.2.5",
			"X-Is-Trusted": "yes",
		},
		"conditions": [
			{
				"type": "regex",
				"match": r"^RemoteAddr: 192.0.2.128:\d+\r?$",
				"negate": False,
			},
			{
				"type": "regex",
				"match": r"^Host: traefik\r?$",
				"negate": False,
			},
		],
	},
	"fail-no-header": {
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
									"ipStrategy": {
										"sourceFallback": True,
									},
								},
							},
						},
					},
				},
			},
		},
		"request_headers": {},
		"conditions": [
			{
				"type": "exact",
				"match": "Forbidden",
				"negate": False,
			},
		],
	},
	"fail-header": {
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
										"depth": 1,
										"header": "X-Custom-Forward-Header",
										"isTrustedHeader": "X-Custom-Trusted-Header",
										"sourceFallback": False,
									},
								},
							},
						},
					},
				},
			},
		},
		"request_headers": {
			"X-Custom-Forward-Header": "10.0.0.5",
			"X-Custom-Trusted-Header": "true",
		},
		"conditions": [
			{
				"type": "exact",
				"match": "Forbidden",
				"negate": False,
			},
		],
	},
	"fail-untrusted-header": {
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
										"depth": 1,
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
		"request_headers": {
			"X-Forwarded-For": "10.0.0.5",
			"X-Is-Trusted": "no",
		},
		"conditions": [
			{
				"type": "exact",
				"match": "Forbidden",
				"negate": False,
			},
		],
	},
	"fail-header-depth": {
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
		"request_headers": {
			"X-Forwarded-For": "127.0.0.50, 10.0.0.5, 192.168.0.0, 192.0.2.5",
			"X-Is-Trusted": "yes",
		},
		"conditions": [
			{
				"type": "exact",
				"match": "Forbidden",
				"negate": False,
			},
		],
	},
}
