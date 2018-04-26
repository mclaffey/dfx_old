#!/usr/bin/env python
import os
import pickle
import logging

# from flask import Flask, redirect, session, url_for, render_template, request, g, flash, send_from_directory, send_file

from flask import Blueprint, g, Flask

bp = Blueprint('frontend', __name__, url_prefix='/bp/<some_val>')

@bp.url_value_preprocessor
def set_data_name(endpoint, values):
    g._some_val = values.pop('some_val')

@bp.route('/val')
def index():
    return g._some_val

# Application

app = Flask(__name__)
app.register_blueprint(bp)
