"""Tyro subcommand implementations, one subcommand per file.

Each function's typed signature is its set of CLI flags (Tyro auto-converts to
kebab-case); the function body only does "parse state → call core.operations →
render result", with all logic living in the core layer.
"""
