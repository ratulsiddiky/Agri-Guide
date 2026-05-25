#!/usr/bin/env bash
set -e

gunicorn --bind=0.0.0.0:${PORT:-8000} app:app
