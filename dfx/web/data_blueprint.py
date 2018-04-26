import os

import pandas as pd
from flask import Blueprint, g, url_for, render_template, request, flash, redirect

from .. import datastore
from .. import describers


# #################################################################################
# Setup and helpers

data_bp = Blueprint('data', '__name__', url_prefix='/data/<data_name>')

@data_bp.url_value_preprocessor
def populate_data_df(endpoint, values):
    g._data_name = values.pop('data_name')
    import pandas as pd
    g._dataframe = pd.read_pickle(df_pickle_path(g._data_name))

def df_pickle_path(data_alias, sub_directory=""):
    return os.path.join(os.getcwd(), '.dfx_data', 'df', sub_directory, "{}.pickle".format(data_alias))

def instance_path(rel_path):
    """Append rel_path to the application's instance folder
    """
    return os.path.join(os.getcwd(), '.dfx_data', rel_path)

def url_for_data(data_method_name, **kwargs):
	"""Convenience function for url_for within data_blueprint

	Instead of:
		url_for('data.something', data_name=g._data_name)
	it's just:
		url_for_data('something')
	"""
	return url_for("data." + data_method_name, data_name = g._data_name, **kwargs)

def get_df():
	return g._dataframe

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        file_path = instance_path('dfx-web-store')
        db = g._database = datastore.DfxStore(file_path)
        #db = g._database = describers.DescriberFactory()
        # now that we have db, set it as the factory for all describers
        describers.factory = db
    return db

def get_commands(df):
    """Generate the command list for the jQuery autocomplete
    """
    commands = []
    commands.extend( [{'label': 'summary', 'value': url_for_data('summary')}] )
    commands.extend( [{'label': 'column {}'.format(col), 'value': url_for_data('column_page', col_name=col)} for col in df.columns] )
    # for col_1 in df.columns:
    #     for col_2 in df.columns:
    #         if col_1 == col_2:
    #             pass
    #         commands.append( {
    #             'label': 'relationship {} {}'.format(col_1, col_2),
    #             'value': url_for_data('relationship_page', col_1_name=col_1, col_2_name=col_2) })
    commands.extend( [{'label': 'reload', 'value': '/reload'}] )
    return commands

def set_describer_url_prefix(describer):
    """Set the url prefix to the paths used by data_blueprint
    """
    describer._url_prefix = "/data/{}".format(g._data_name)


# #################################################################################
# View functions


@data_bp.route('/')
def summary():
    db = get_db()
    df = get_df()
    describer = db.get_or_create(describers.TablePageDescriber, df)
    set_describer_url_prefix(describer)
    g.commands = get_commands(df)
    return render_template('table.html',
        describer = describer,
        )

@data_bp.route('/column/<string:col_name>')
def column_page(col_name):
    df = get_df()
    col_index = list(df.columns).index(col_name)
    #cols = get_columns()
    cols = {col: None for col in df.columns}
    col_level = cols.get(col_name, None)

    # navigation - previous column
    if col_index == 0:
        prev_col = None
        prev_col_hyperlink = None
    else:
        prev_col = df.columns[col_index-1]
        prev_col_hyperlink = url_for_data('column_page', col_name=prev_col)
    # navigation - next column
    if col_index == len(df.columns)-1:
        next_col = None
        next_col_hyperlink = None
    else:
        next_col = df.columns[col_index+1]
        next_col_hyperlink = url_for_data('column_page', col_name=next_col)
    # helper dictionary
    helper_d = dict(
        col_name = col_name,
        prev_col_hyperlink = prev_col_hyperlink,
        next_col_hyperlink = next_col_hyperlink,
        )

    db = get_db()
    describer = db.get_or_create(describers.ColumnPageDescriber, df, col_name)
    set_describer_url_prefix(describer)
    g.commands = get_commands(df)

    return render_template('column.html', 
        #col_index=col_index, 
        col_level=col_level, 
        describer = describer,
        helper_d = helper_d,
        )

@data_bp.route('/row/<int:row_num>')
def row_page(row_num):    
    df = get_df()
    db = get_db()
    describer = db.get_or_create(describers.RowPageDescriber, df, row_num)
    set_describer_url_prefix(describer)
    g.commands = get_commands(df)

    return render_template('row.html', 
        describer = describer,
        row_num = row_num,
        )

@data_bp.route('/column/modify', methods=['POST'])
def column_modify():
    """Set properties of a column
    """
    col_name = request.form.get('col_name', None)
    if col_name is None:
        raise ValueError("no col_name")
    action = request.form.get('action', None)

    df = get_df()
    cols = get_columns()
    col_level = cols.get(col_name, None)

    if action == 'promote':
        if col_level is None or col_level <= 1:
            col_level = 1
        else:
            col_level -= 1
    if action == 'demote':
        if col_level is None or col_level >= 3:
            col_level = 3
        else:
            col_level += 1
    cols[col_name] = col_level

    return redirect(url_for('column_page', col_name=col_name))

@data_bp.route('/column/<string:col_1_name>/relates-to/<string:col_2_name>')
def relationship_page(col_1_name, col_2_name):
    df = get_df()
    g.commands = get_commands(df)
    db = get_db()
    describer = db.get_or_create(describers.RelationshipPageDescriber, df, col_1_name, col_2_name)
    set_describer_url_prefix(describer)
    return render_template('relationship.html', describer = describer)

@data_bp.route('/column/<string:col_name>/values/<string:val>')
def value_page(col_name, val):
    df = get_df()
    g.commands = get_commands(df)
    db = get_db()
    describer = db.get_or_create(describers.ValuePageDescriber, df, col_name, val)
    set_describer_url_prefix(describer)
    return render_template('value.html', describer = describer)

@data_bp.route('/rename', methods=['POST'])
def rename():
    """Rename a dataset picke file
    """
    old_name = g._data_name
    old_path = df_pickle_path(old_name)
    new_name = request.form['new_data_alias']
    new_path = df_pickle_path(new_name)
    os.rename(old_path, new_path)
    flash('Renamed data from {} to {}'.format(old_name, new_name))
    g._data_name = new_name
    return redirect(url_for_data('summary'))

@data_bp.route('/delete', methods=['POST'])
def delete():
    """Move a dataset picke file to instance/df/recycle
    """
    old_path = df_pickle_path(g._data_name)
    new_path = df_pickle_path(g._data_name, sub_directory="recycle")
    os.rename(old_path, new_path)
    flash('Moved data {} to recyling bin'.format(g._data_name))
    return redirect(url_for('home'))



