_URL_PREFIX = "/dfxweb"

class UrlMaker(object):
    """For columns, rows and other things, generate a url 

    _prefix

        Every URL generated has _prefix appended at the beginning. This is intended as a search-and-replace
        string, so that the web server can replace that prefix with whatever the base URL is. For example,
        if the server is using URLs like http://server.com/myserver/data/some_data/column/record_id, the server
        can use page_html.replace('/dfxweb', '/myserver/data/some_data')

    """
    _prefix = _URL_PREFIX

    def column(self, col_name):
        return "<a href='{prefix:}/column/{col_name:}'>{col_name:}</a>".format(prefix=self._prefix, col_name = col_name)

    def row(self, row_index):
        return "<a href='{prefix:}/column/{row_index:}'>{row_index:}</a>".format(prefix=self._prefix, row_index = row_index)

    def relationship(self, col_1_name, col_2_name):
        """Given two column names, generate the hyperlink to the relationship
        """
        return "<a href='{prefix:}/column/{col_1_name:}/relates-to/{col_2_name:}'>{col_1_name:}-{col_2_name:}</a>".format(
            prefix=self._prefix, 
            col_1_name = col_1_name,
            col_2_name = col_2_name)

    def column_value(self, col_name, value):
        """Given a value in a specific column, generate a hyperlink to that page
        """
        return "<a href='{prefix:}/column/{col_name:}/values/{value:}'>{value:}</a>".format(
            prefix=self._prefix, 
            col_name = col_name,
            value = value,)

def df_to_html(df, urls):
    """Convert a pandas dataframe to HTML like .to_html(), but customized
    """
    html = []
    html.append("<table border='1' class='dfx-table'>")
    html.append("  <thead>")
    html.append("    <tr>")
    html.append("      <th>row</th>")
    for col in df.columns:
        col_text = urls.column(col)
        html.append("      <th>{}</th>".format(col_text))
    html.append("    </tr>")
    html.append("  </thead>")
    html.append("  <tbody>")
    for (i, row) in df.iterrows():
        html.append("    <tr>")
        html.append("      <td><a href='/row/{row_num:}'>{row_num:}</a></td>".format(row_num=i))
        for val in row:
            html.append("      <td>{}</td>".format(val))
        html.append("    </tr>")
    html.append("  </tbody>")
    html.append("</table>")
    
    return "\n".join(html)

def df_to_html_value_counts(df, col_name, urls):
    """For a pandas.count_values() dataframe, like .to_html() but with links to values
    """
    html = []
    html.append("<table border='1' class='dfx-table'>")
    html.append("  <thead>")
    html.append("    <tr>")
    for col in df.columns:
        html.append("      <th>{}</th>".format(col))
    html.append("    </tr>")
    html.append("  </thead>")
    html.append("  <tbody>")
    for (i, row) in df.iterrows():
        html.append("    <tr>")
        html.append("      <td>{}</td>".format(urls.column_value(col_name, row[0])))
        html.append("      <td>{}</td>".format(row[1]))
        html.append("    </tr>")
    html.append("  </tbody>")
    html.append("</table>")
    
    return "\n".join(html)

def df_to_html_column_highlighted(df, col_name, urls):
    """Convert a pandas dataframe to HTML like .to_html(), but highlight a column
    """
    col_index = list(df.columns).index(col_name)
    html = []
    html.append("<table border='1' class='dfx-table'>")
    html.append("  <thead>")
    html.append("    <tr>")
    html.append("      <th>row</th>")
    for col in df.columns:
        col_text = urls.column(col)
        if col==col_name:
            highlight_class = "class='dfx-column-highlight'"
        else:
            highlight_class = ""
        html.append("      <th {}>{}</th>".format(highlight_class, col_text))
    html.append("    </tr>")
    html.append("  </thead>")
    html.append("  <tbody>")
    for (i, row) in df.iterrows():
        html.append("    <tr>")
        html.append("      <td>{}</td>".format(i))
        for (j, val) in enumerate(row):
            if j==col_index:
                highlight_class = "class='dfx-column-highlight'"
            else:
                highlight_class = ""
            html.append("      <td {}>{}</td>".format(highlight_class, val))
        html.append("    </tr>")
    html.append("  </tbody>")
    html.append("</table>")
    
    return "\n".join(html)

def df_to_html_hierarchy(df, urls):
    """Uses by RelationshipOneToMany
    """
    html = []
    html.append("<table border='1' class='dfx-table'>")
    html.append("  <thead>")
    html.append("    <tr>")
    for col in df.columns:
        if col == 'row_count':
            col_text = col
        else:
            col_text = urls.column(col)
        html.append("      <th>{}</th>".format(col_text))
    html.append("    </tr>")
    html.append("  </thead>")
    html.append("  <tbody>")
    for (i, row) in df.iterrows():
        html.append("    <tr>")
        html.append("      <td>{}</td>".format(urls.column_value(df.columns[0], row[0])))
        html.append("      <td>{}</td>".format(urls.column_value(df.columns[1], row[1])))
        html.append("      <td>{}</td>".format(row[2]))
        html.append("    </tr>")
    html.append("  </tbody>")
    html.append("</table>")
    
    return "\n".join(html)


