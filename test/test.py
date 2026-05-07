#!/usr/bin/env python3

from typing import TypedDict
import signal
import sys
import pathlib
import re
import subprocess
import os

from src import docker
from src import config
from src import runner
import test_definitions

BASE_REPO_DIR = "../"

d = None # Docker instance

class PluginInfo(TypedDict):
	name: str
	version: str
	module_name: str
	repo_dir: pathlib.Path

def signal_handler(signalnum, _):
	signal.signal(signalnum, signal.SIG_IGN)
	cleanup()
	sys.exit(0)

def configure(mode: str, plugin: PluginInfo, config: config.ConfigOptions) -> config.ConfigOptions:
	config["whoami_extra_labels"] += [f"traefik.http.routers.whoami.middlewares={plugin["name"]}@file"]
	if mode == "production":
		if plugin["version"] is None:
			print("Unable to find version of plugin!")
			sys.exit(1)
		config["traefik_extra_config"] |= {"experimental": {
			"plugins": {
				plugin["name"]: {
					"moduleName": plugin["module_name"],
					"version": plugin["version"],
				}
			}
		}}
		print(f"Testing production plugin [{plugin["module_name"]}] version [{plugin["version"]}]")
	else:
		if mode != "development":
			print(f"Unknown mode [{mode}], falling back to development")
		mode = "development"
		config["traefik_extra_volumes"].append(f"{str(plugin["repo_dir"])}:/plugins-local/src/{plugin["module_name"]}:ro")
		config["traefik_extra_config"] |= {"experimental": {
			"localPlugins": {
				plugin["name"]: {
					"moduleName": plugin["module_name"],
				}
			}
		}}
		print(f"Testing development plugin [{plugin["module_name"]}]")
	return config

def discover_plugin(base_dir) -> PluginInfo:
	repo_dir = (base_dir / BASE_REPO_DIR).resolve()
	module_name = re.search(r"^module (.+)$", pathlib.Path(repo_dir / "go.mod").resolve().read_text(), re.MULTILINE).group(1)
	name = re.search(r"^.+/.+/(.+)$", module_name).group(1)

	version = None
	try:
		version = subprocess.check_output(["git", "describe", "--match", "v*", "--abbrev=0", "--tags", "HEAD"], cwd=str(repo_dir), stderr=subprocess.DEVNULL).decode("utf-8").strip()
	except:
		pass
		
	return {
		"name": name,
		"version": version,
		"module_name": module_name,
		"repo_dir": repo_dir,
	}

def main() -> None:
	signal.signal(signal.SIGINT, signal_handler)
	signal.signal(signal.SIGTERM, signal_handler)

	run_mode = "development"
	target_test = None
	if len(sys.argv) >= 2:
		run_mode = sys.argv[1]
	if len(sys.argv) >= 3:
		target_test = sys.argv[2]
		print(f"Running single test [{target_test}]")

	base_dir = pathlib.Path(__file__).resolve().parent
	plugin = discover_plugin(base_dir)

	work_dir = base_dir / "work"
	work_dir.mkdir(parents=True, exist_ok=True)
	log_dir = work_dir / "logs"
	log_dir.mkdir(parents=True, exist_ok=True)
	config_dir = base_dir / "config"
	print(f"Work dir [{work_dir}]")

	c = config.Config(configure(run_mode, plugin, {
		"docker_base_config": config_dir / "docker-compose.base.yml",
		"docker_runtime_config": work_dir / "docker-compose.yml",
		"traefik_base_config": config_dir / "traefik.base.yml",
		"traefik_runtime_config": work_dir / "traefik.yml",
		"middleware_config_dir": work_dir / "traefik_config",
		"logs_dir": log_dir,
		"output_dir": base_dir / "output",

		"traefik_extra_volumes": [],
		"traefik_extra_config": {},
		"whoami_extra_labels": [],
	}))

	c.gen_static_config()

	# Empty output dir
	for root, dirs, files in c.get_options()["output_dir"].walk(top_down=False):
		for name in files:
			(root / name).unlink()
		for name in dirs:
			(root / name).rmdir()

	global d
	d = docker.Docker(c.get_options()["docker_runtime_config"], cwd=str(work_dir))

	if "TRAEFIK_WHOAMI_VERSION" not in os.environ:
		print("Using Traefik whoami version [latest]")
	else:
		print(f"Using Traefik whoami version [{os.environ["TRAEFIK_WHOAMI_VERSION"]}]")
	if "TRAEFIK_VERSION" not in os.environ:
		print("Using Traefik version [latest]")
	else:
		print(f"Using Traefik version [{os.environ["TRAEFIK_VERSION"]}]")
	print()

	d.pull()

	all_result = True
	failed_tests = []
	
	for name, conf in test_definitions.TESTS.items():
		if target_test is None or target_test == name:
			print(f"Running test [{name}]")
			c.gen_config(conf)
			d.start()

			result = runner.run(c.get_options(), name, conf, d)
			print(f"Test [{name}] result: {"success" if result else "fail"}")
			all_result = all_result and result
			if not result:
				failed_tests.append(name)

			d.stop_service("traefik")

			runner.archive(c.get_options(), name, conf)

	cleanup()
	print("All tests completed")
	print(f"Final result: {"success" if all_result else "fail"}")
	if not all_result:
		print("Failed tests:")
		for name in failed_tests:
			print(f"  - {name}")
	sys.exit(0 if all_result else 10)

def cleanup() -> None:
	print("Cleaning up...")
	d.stop()

if __name__ == '__main__':
	main()
