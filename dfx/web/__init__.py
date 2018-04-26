#!/usr/bin/env python
import os
import pickle
import logging

from flask import Flask, redirect, session, url_for, render_template, request, g, flash, send_from_directory, send_file, Blueprint

# from dfx
from .data_blueprint import data_bp, df_pickle_path

# #################################################################
# Data Blueprint


app = Flask(__name__, instance_relative_config=True)
app.secret_key = '1>k\x07\xf7\xe6\xeflO\x9e\x80\x9c\xc7qp\xef\xed2\xfc9$\x10\xbbr'
app.register_blueprint(data_bp)

# #################################################################
# helpers

def instance_path(rel_path=''):
    """Append rel_path to the application's instance folder
    """
    return os.path.join(os.getcwd(), '.dfx_data', rel_path)

def setup_instance():
    for dir in [instance_path(), instance_path('df')]:        
        if not os.path.exists(dir):
            os.makedirs(dir)

setup_instance()

# #################################################################
# logging

logger = logging.getLogger(__name__)
logger_dfx = logging.getLogger('dfx')

def setup_logging():
    f = logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
        datefmt = "%Y-%m-%d %I:%M %S")
    sh = logging.StreamHandler()
    sh.setFormatter(f)
    fh = logging.FileHandler(instance_path('log.txt'))
    fh.setFormatter(f)
    logger_dfx.handlers = [sh, fh]
    logger_dfx.setLevel(logging.DEBUG)

setup_logging()

# ########################################################################
# Main pages

@app.route('/')
def home():
    candidate_files = os.listdir(instance_path('df'))
    data_names = [_[:-len('.pickle')] for _ in candidate_files if _.endswith('.pickle')]
    files = build_file_links('')

    # build commands
    g.commands = []
    for data_name in data_names:
        g.commands.append({
            'label': "data {}".format(data_name),
            'value': url_for('data.summary', data_name=data_name)
            })
    for file_name, file_url in files:
        if file_url is not None:
            g.commands.append({
                'label': "file {}".format(file_name),
                'value': file_url,
                })

    return render_template('home.html',        
        data_names = data_names,
        files = files,
        )

@app.route('/data')
def data_sets():
    return home()

@app.route('/reload')
def reload():
    db = get_db()
    db.delete_all()
    return redirect(url_for('home'))

# ########################################################################
# File nav

def build_file_links(sub_path):
    """Build a list of (file_name, url)

    Used by both home() and file_navigate()
    """
    files = []
    full_path = os.path.join(os.getcwd(), sub_path)
    file_names = os.listdir(full_path)
    for file_name in file_names:
        file_path = os.path.join(sub_path, file_name)
        # links for sub directories or recognized file types
        if os.path.isdir(file_path) or file_name.endswith('.csv'):
            files.append( (
                file_name,
                url_for('file_navigate', sub_path=os.path.join(sub_path, file_name))
                ))
        else:
            files.append( (file_name, None))

    return files

@app.route('/files')
@app.route('/files/')
@app.route('/files/<path:sub_path>')
def file_navigate(sub_path = ''):
    """Navigate directory structure and load files
    """
    if not os.path.exists(sub_path):
        flash("File path does not exist: {}".format(sub_path))
        return redirect(url_for('file_navigate'))

    if os.path.isdir(sub_path):
        # if directory, file navigation
        files = build_file_links(sub_path)
        # commands
        g.commands = [{'value': '/', 'label': 'home'}]
        for file_name, file_url in files:
            if file_url is not None:
                g.commands.append({
                    'label': "file {}".format(file_name),
                    'value': file_url,
                    })
        return render_template("file_nav.html", files = files)
    else:
        # if file, load form
        suggested_alias = os.path.splitext(os.path.basename(sub_path))[0]
        return render_template('file_load.html', file_path = sub_path, suggested_alias = suggested_alias)



@app.route('/load_data_file', methods=["POST"])
def load_file():
    data = request.form
    data_path = data['data_path']
    data_alias = data['data_alias']
    logger.info('load_file() {} as {}'.format(data_path, data_alias))

    # import data and save pickle
    import pandas as pd
    df = pd.read_csv(data_path, encoding='utf-8')
    df_path = df_pickle_path(data_alias)
    df.to_pickle(df_path)

    return redirect(url_for('data.summary', data_name = data_alias))



