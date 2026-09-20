#!/bin/bash
# Installs dependencies into the layout DigitalOcean's Python runtime expects.
#
# Always deploy with --remote-build. pydantic-core (via fastapi) ships compiled
# wheels, so a build on this Mac would produce arm64/macOS artifacts that the
# Linux runtime cannot load. --remote-build runs this on DigitalOcean instead.
#
# The Python version is read from the build container rather than hardcoded, so
# this keeps working when python:default moves.
set -e

PYV=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
virtualenv --without-pip virtualenv
pip install -r requirements.txt --target "virtualenv/lib/python${PYV}/site-packages"
