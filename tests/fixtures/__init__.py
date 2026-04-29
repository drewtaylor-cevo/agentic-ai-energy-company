"""Test fixtures not auto-loaded by pytest conftest — explicit-import only.

Modules in this package are intentionally NOT auto-registered so that
unit tests that don't need heavyweight fixtures (e.g. mock-Bedrock) are
not forced to import them. Use explicit
`from tests.fixtures.mocked_model_provider import MockedModelProvider`
in tests that need them.
"""
