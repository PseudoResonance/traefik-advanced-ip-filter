from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString
from collections.abc import Mapping

yaml=YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.default_flow_style = False

from src import config

def run(config: config.ConfigOptions, state: config.ConfigState, name: str, options: config.TestOptions) -> bool:
	result = run_test(config, state, name, options)
	(config["logs_dir"] / "result.txt").write_text("success" if result else "fail")
	return result

# Mutates input dict
def make_strings_scalars(data: dict[str, any]) -> dict[str, any]:
	for k, v in data.items():
		if isinstance(v, Mapping):
			make_strings_scalars(v)
		elif isinstance(v, str):
			if "\n" in v.strip():
				data[k] = LiteralScalarString(v.strip())
	return data


def run_test(config: config.ConfigOptions, state: config.ConfigState, name: str, options: config.TestOptions) -> bool:
	proxy = {
		"http": f"socks5://{state["proxy_host_address"]}:{state["proxy_host_port"]}",
		"https": f"socks5://{state["proxy_host_address"]}:{state["proxy_host_port"]}",
	}
	result, data =  options["action"]["run"]({
		"v4": {
			"ip": state["traefik_ipv4"],
			"url": f"http://{state["traefik_ipv4"]}:80",
		},
		"v6": {
			"ip": state["traefik_ipv6"],
			"url": f"http://[{state["traefik_ipv6"]}]:80",
		},
	}, {
		"v4": state["proxy_ipv4"],
		"v6": state["proxy_ipv6"],
	}, proxy)
	with (config["logs_dir"] / "request.yml").open(mode="w", encoding="utf-8") as f:
		yaml.dump(make_strings_scalars(data), f)
	return result

def archive(config: config.ConfigOptions, name: str, options: config.TestOptions) -> None:
	config["output_dir"].mkdir(parents=True, exist_ok=True)
	d = (config["output_dir"] / name)
	d.mkdir(parents=True, exist_ok=True)

	logs = d / "logs"
	logs.mkdir(parents=True, exist_ok=True)

	for root, _, files in config["logs_dir"].walk(top_down=False):
		for name in files:
			(root / name).rename(logs / name)
