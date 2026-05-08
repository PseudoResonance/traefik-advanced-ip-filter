#!/usr/bin/env python3

from typing import List, TypedDict
import signal
import sys
import pathlib
import re
import subprocess
import os
import time
import runpy
import traceback

from src import docker
from src import config
from src import runner

BASE_REPO_DIR = "../"

d = None # Docker instance

class TestInfo(TypedDict):
	name: str
	file: pathlib.Path
	definition: config.TestOptions

class PluginInfo(TypedDict):
	name: str
	version: str
	module_name: str
	repo_dir: pathlib.Path

def signal_handler(signalnum, _):
	signal.signal(signalnum, signal.SIG_IGN)
	cleanup()
	sys.exit(0)

def load_tests(test_dir: pathlib.Path) -> dict[str, TestInfo]:
	all_tests: dict[str, TestInfo] = dict()
	for root, _, files in test_dir.walk(top_down=True):
		if root != test_dir:
			break
		for f in files:
			if (root / f).suffix == ".py":
				print(f"Loading tests from [{(root / f).name}]")
				output = runpy.run_path(str(root / f))
				if "TESTS" in output:
					for k, v in output["TESTS"].items():
						if k in all_tests:
							print(f"Test [{k}] was already loaded by [{all_tests[k]["file"].name}]")
							sys.exit(2)
						all_tests[k] = {
							"name": k,
							"file": root / f,
							"definition": v,
						}
	
	return all_tests
				

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
	test_dir = base_dir / "tests"
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

	state = c.gen_static_config()

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

	tests = load_tests(test_dir)

	all_result = True
	failed_tests: List[TestInfo] = []
	
	for name, info in tests.items():
		if target_test is None or target_test == name:
			result = False
			try:
				print(f"Running test [{name}]")
				c.gen_config(info["definition"])
				d.start()

				time.sleep(2) # Traefik is slow sometimes...

				result = runner.run(c.get_options(), state, name, info["definition"])
			except Exception as e:
				result = False
				print(f"Exception while executing test {info["name"]} from {info["file"].name}\n{e}")
				print(traceback.format_exc())
			finally:
				print(f"Test [{name}] result: {"success" if result else "fail"}")
				all_result = all_result and result
				if not result:
					failed_tests.append(info)

				d.stop_service("traefik")

				runner.archive(c.get_options(), name, info["definition"])

	cleanup()
	print("All tests completed")
	print(f"Final result: {"success" if all_result else "fail"}")
	if not all_result:
		print("Failed tests:")
		for info in failed_tests:
			print(f"  - {info["name"]} from {info["file"].name}")
	sys.exit(0 if all_result else 10)

def cleanup() -> None:
	print("Cleaning up...")
	d.stop()

if __name__ == '__main__':
	main()
