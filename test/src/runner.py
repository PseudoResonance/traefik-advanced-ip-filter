import sys
import re

from src import config
from src import docker

def run(config: config.ConfigOptions, name: str, options: config.TestOptions, docker: docker) -> bool:
	header_args = []
	for k, v in options["request_headers"].items():
		header_args.append("-H")
		header_args.append(f"{k}:{v}")
	output = docker.exec("client", ["curl", "-s", *header_args, "http://traefik:80/"]).strip()
	(config["logs_dir"] / "curl.txt").write_text(output)
	result = check_conditions(options, output)
	(config["logs_dir"] / "result.txt").write_text("success" if result else "fail")
	return result

def check_conditions(options: config.TestOptions, output: str) -> bool:
	result = True
	for c in options["conditions"]:
		if c["type"] == "exact":
			result = result and ((output == c["match"]) ^ c["negate"])
		elif c["type"] == "regex":
			result = result and ((re.search(c["match"], output, re.MULTILINE) is not None) ^ c["negate"])
		else:
			print(f"Unknown condition type [{c["type"]}]")
			sys.exit(1)
		if not result:
			return False
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
