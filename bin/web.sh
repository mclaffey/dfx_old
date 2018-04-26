#!/bin/bash
export FLASK_APP=dfx/web/__init__.py

export FLASK_DEBUG=1

open "http://127.0.0.1:5000"

flask run
