#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main() -> None:
    """Run administrative tasks using local development settings by default."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Did you install the project dependencies?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
