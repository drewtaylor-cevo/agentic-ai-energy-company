# This file makes lambda/ importable as a Python package for unit tests.
# The file is not included in the Lambda deployment zip (excluded via .gitignore
# would not work — instead, CDK's Code.from_asset excludes __init__.py by default
# since it only picks up what's in the directory). For local testing purposes,
# having __init__.py allows `importlib.import_module("lambda.handler")` to resolve.
