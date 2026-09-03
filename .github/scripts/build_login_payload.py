#!/usr/bin/env python3
"""Prints the JSON body for POST /v1/auth/login, reading the password from the
RELAYHUB_TEST_ACCOUNT_PASSWORD env var (a GitHub Actions secret) so it never
appears in the workflow YAML or command-line arguments. Kept as a real script
file rather than embedded inline in the workflow -- see report_delivery_status.py's
docstring for why embedding multi-line Python in a YAML block scalar is fragile."""
import json
import os

print(json.dumps({"email": "sahilkhan67sh@gmail.com", "password": os.environ["RELAYHUB_TEST_ACCOUNT_PASSWORD"]}))
