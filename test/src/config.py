from typing import TypedDict, List, Literal, Union
import yaml
import pathlib

class ExactCondition(TypedDict):
	type: Literal["exact"]
	match: str
	negate: bool

class RegexCondition(TypedDict):
	type: Literal["regex"]
	match: str
	negate: bool

TestCondition = Union[ExactCondition, RegexCondition]

class TestOptions(TypedDict):
	traefik_extra_config: dict
	traefik_middleware_config: dict[str, dict]
	request_headers: dict[str, str]
	conditions: List[TestCondition]

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

class Config:
	def __init__(self, options: ConfigOptions):
		self.options = options
	
	def get_options(self) -> ConfigOptions:
		return self.options

	def gen_static_config(self):
		docker_config = yaml.safe_load(self.options["docker_base_config"].read_text())
		docker_config["services"]["traefik"]["volumes"] += self.options["traefik_extra_volumes"]
		docker_config["services"]["whoami"]["labels"] += self.options["whoami_extra_labels"]
		self.options["docker_runtime_config"].write_text(yaml.dump(docker_config, indent=2))
		self.options["middleware_config_dir"].mkdir(parents=True, exist_ok=True)
	
	def setup_run(self, options: TestOptions):
		self.options["logs_dir"].mkdir(parents=True, exist_ok=True)
		(self.options["logs_dir"] / "traefik.log").touch()
		(self.options["logs_dir"] / "debug.log").touch()
		(self.options["logs_dir"] / "access.log").touch()

	def gen_config(self, options: TestOptions):
		traefik_config = yaml.safe_load(self.options["traefik_base_config"].read_text())
		traefik_config_full = traefik_config | self.options["traefik_extra_config"] | options["traefik_extra_config"]
		self.options["traefik_runtime_config"].write_text(yaml.dump(traefik_config_full, indent=2))

		for root, _, files in self.options["middleware_config_dir"].walk(top_down=False):
			for name in files:
				(root / name).unlink()
		for name, data in options["traefik_middleware_config"].items():
			(self.options["middleware_config_dir"] / name).write_text(yaml.dump(data, indent=2))
		self.setup_run(options)
