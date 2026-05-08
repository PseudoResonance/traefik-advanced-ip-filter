from typing import TypedDict, List, Callable, Tuple
from collections.abc import MutableMapping
from ruamel.yaml import YAML
import pathlib

yaml=YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.default_flow_style = False

class BaseUrl(TypedDict):
	ip: str
	url: str

class AllBaseUrls(TypedDict):
	v4: BaseUrl
	v6: BaseUrl

class Addresses(TypedDict):
	v4: str
	v6: str

class TestActions(TypedDict):
	run: Callable[[AllBaseUrls, Addresses, MutableMapping[str, str]], Tuple[bool, str]]

class TestOptions(TypedDict):
	traefik_extra_config: dict
	traefik_middleware_config: dict[str, dict]
	action: TestActions # Inputs (base_urls: AllBaseUrls, client_ips: Addresses, proxy: MutableMapping[str, str])

class ConfigOptions(TypedDict):
	docker_base_config: pathlib.Path
	docker_runtime_config: pathlib.Path
	traefik_base_config: pathlib.Path
	traefik_runtime_config: pathlib.Path
	middleware_config_dir: pathlib.Path
	logs_dir: pathlib.Path
	output_dir: pathlib.Path

	traefik_extra_volumes: List[str]
	traefik_extra_config: dict
	whoami_extra_labels: List[str]

class ConfigState(TypedDict):
	traefik_ipv4: str
	traefik_ipv6: str
	proxy_host_port: int
	proxy_host_address: str
	proxy_ipv4: str
	proxy_ipv6: str

class Config:
	def __init__(self, options: ConfigOptions):
		self.options = options
	
	def get_options(self) -> ConfigOptions:
		return self.options

	def gen_static_config(self) -> ConfigState:
		state: ConfigState = {
			"traefik_ipv4": "traefik",
			"traefik_ipv6": "traefik",
			"proxy_host_port": 1080,
			"proxy_host_address": "localhost",
			"proxy_ipv4": "192.0.2.64",
			"proxy_ipv6": "cfff:d518:1358:3724:1e59:ddd8:9586:1acd",
		}
		docker_config = None
		with self.options["docker_base_config"].open(mode="r", encoding="utf-8") as f:
			docker_config = yaml.load(f)
		docker_config["services"]["traefik"]["volumes"] += self.options["traefik_extra_volumes"]
		docker_config["services"]["whoami"]["labels"] += self.options["whoami_extra_labels"]
		self.options["middleware_config_dir"].mkdir(parents=True, exist_ok=True)

		if "ipv4_address" in docker_config["services"]["traefik"]["networks"]["net"]:
			state["traefik_ipv4"] = docker_config["services"]["traefik"]["networks"]["net"]["ipv4_address"]
		if "ipv6_address" in docker_config["services"]["traefik"]["networks"]["net"]:
			state["traefik_ipv6"] = docker_config["services"]["traefik"]["networks"]["net"]["ipv6_address"]

		if "ipv4_address" in docker_config["services"]["proxy"]["networks"]["net"]:
			state["proxy_ipv4"] = docker_config["services"]["proxy"]["networks"]["net"]["ipv4_address"]
		if "ipv6_address" in docker_config["services"]["proxy"]["networks"]["net"]:
			state["proxy_ipv6"] = docker_config["services"]["proxy"]["networks"]["net"]["ipv6_address"]

		if "ports" in docker_config["services"]["proxy"]:
			for v in docker_config["services"]["proxy"]["ports"]:
				if "name" in v and v["name"] == "ingress":
					if "published" in v:
						state["proxy_host_port"] = int(v["published"])
					if "host_ip" in v:
						state["proxy_host_address"] = v["host_ip"]
					break

		with self.options["docker_runtime_config"].open(mode="w", encoding="utf-8") as f:
			yaml.dump(docker_config, f)
		return state
	
	def setup_run(self, options: TestOptions):
		self.options["logs_dir"].mkdir(parents=True, exist_ok=True)
		(self.options["logs_dir"] / "traefik.log").touch()
		(self.options["logs_dir"] / "debug.log").touch()
		(self.options["logs_dir"] / "access.log").touch()

	def gen_config(self, options: TestOptions):
		traefik_config = None
		with self.options["traefik_base_config"].open(mode="r", encoding="utf-8") as f:
			traefik_config = yaml.load(f)
		traefik_config_full = traefik_config | self.options["traefik_extra_config"] | options["traefik_extra_config"]
		with self.options["traefik_runtime_config"].open(mode="w", encoding="utf-8") as f:
			yaml.dump(traefik_config_full, f)

		for root, _, files in self.options["middleware_config_dir"].walk(top_down=False):
			for name in files:
				(root / name).unlink()
		for name, data in options["traefik_middleware_config"].items():
			with (self.options["middleware_config_dir"] / name).open(mode="w", encoding="utf-8") as f:
				yaml.dump(data, f)
		self.setup_run(options)
