from typing import Sequence
import subprocess

class Docker:
	def __init__(self, compose_path: str, cwd: str = None, env: dict[str, str] = None):
		self.compose_path = compose_path
		self.cwd = cwd
		self.env = env
		self.base_args = ["docker", "compose", "-f", str(self.compose_path)]
	
	def pull(self) -> None:
		subprocess.check_output(self.base_args + ["pull"], cwd=self.cwd, env=self.env)
	
	def start(self) -> None:
		subprocess.check_output(self.base_args + ["up", "-d", "--wait"], cwd=self.cwd, env=self.env)
	
	def stop(self) -> None:
		subprocess.check_output(self.base_args + ["down", "-v", "--remove-orphans"], cwd=self.cwd, env=self.env)
	
	def stop_service(self, service: str) -> None:
		subprocess.check_output(self.base_args + ["stop", service], cwd=self.cwd, env=self.env)
	
	def exec(self, service: str, args: Sequence[str]) -> str:
		return subprocess.check_output(self.base_args + ["exec", service, *args], cwd=self.cwd, env=self.env).decode("utf-8")
