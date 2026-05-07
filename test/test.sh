#!/usr/bin/env sh

cd "$(dirname "$0")"

if ! test -d ./.venv; then
	python3 -m venv "./.venv"
	./.venv/bin/pip install -r requirements.txt
fi

./.venv/bin/python3 test.py "$@"
