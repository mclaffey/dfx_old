import os
import enum
import random

import jinja2
import numpy as np # for is_numeric()
import pandas.util # for get_df_hash()
import pandas as pd

from . import html as dfx_html

_IMAGE_BASE_PATH = ''

# see helpers at bottom for on-demand imports: numpy, pandas.util

"""

# Dataframe                 - initialized with (df)
Describer                   - abstract
ShapeColumns                - discrete implementation
ShapeRows                   - discrete implementation
TablePageDescriber          - collection for html

# Column                    - initialized with (df, col_name)
ColumnDescriber             - abstract
ColumnId                    - discrete implementation
ColumnCategorical           - discrete implementation
ColumnText                  - discrete implementation
ColumnNumeric               - discrete implementation
ColumnPageDescriber         - collection for html

# Relationship              - initialized with (df, col1, col2)
RelationshipDescriber       - abstract
RelationshipAnova           - discrete implementation
RelationshipPageDescriber   - collection for html

# Row                       - initialized with (df, row_index)
RowPageDescriber             - html page

# Value                     - initialized with (df, col_name, value)
??

"""

# #######################################################################################
# Logging - No logging implemented as of 4/29/2018

# logger = logging.getLogger(__name__)

# #######################################################################################
# Jinja

_template_dir = os.path.join(os.path.dirname(__file__), 'templates/')
if not os.path.exists(_template_dir):
    raise ValueError("Template directory does not exist", _template_dir)
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(_template_dir),
    # autoescape=select_autoescape(['html', 'xml'])
)

# #######################################################################################
# Describer Factory

class DescriberFactory(object):
    """Given a class and arguments, create a describer instance

    This implementation doesn't add any value, but it is intended to be replaceable
    with DfxStore using:
        dfx.describers.factory = dfx.datastore.DfxStore('some/file')

    This allows DfxStore to retrieve any describer that has already been calculated,
    whereas this factory has to calculate from scratch every describer it creates.

    """
    def get_or_create(self, klass, df, *args):
        return klass(df, *args)

factory = DescriberFactory()

# #######################################################################################
# Describer State


class State(enum.Enum):
    UNCALCULATED = 1
    INVALID = 2
    UNQUALIFIED = 3
    QUALIFIED = 4
    def __eq__(self, other):
        if self.__class__ != other.__class__:
            raise NotImplemented
        return self.value == other.value
    def __lt__(self, other):
        if self.__class__ != other.__class__:
            raise NotImplemented
        return self.value < other.value
    def __gt__(self, other):
        if self.__class__ != other.__class__:
            raise NotImplemented
        return self.value > other.value


# #######################################################################################
# Abstract Describer

class Describer(object):
    """The abstract framework for describing a dataframe

    Usage:
        d = Describer(df)
        if d.valid:
            print d.description
            print d.html

    .valid
        whether the calculation ran successfully. If it didn't, the describer probably
        isn't appropriate for the given data and isn't relevant.

    .qualified
        if the describer tests for a specific property, this conveys whether that property
        was met. Describers with qualified=true are expected to be more interesting, but
        knowing qualified=false could still be relevant/useful.

        If not valid, assume not qualified.

    .description
        A human readable message about the data. Generally intended to be a single string.

    .html
        A verbose, comprehensive description of that data, leveraging html elements like
        tables and hyperlinks.

    .suppresses(hash)
        Determine if one describer recommends not reporting another describer.

        Some describers can only be true if a more generic desriber is also true. For example, if one
        describer identifies a column as a normally distributed number, then a second describer that
        simply identifies a column as being numeric must also be true. Reporting the second wouldn't
        provide any additional information. In this case, the normally distributed describer would
        recommend suppressing the numeric describer.

        Usage:
            numeric = NumericDecsriber(df, 'value')
            normal = NormallyDistributedDecsriber(df, 'value')
            normal._suppresses(numeric) # True
            numeric._suppresses(normal) # False

    --- Behind the scenes

    .hash
        A string describing the class and initializing arguments, used by the dfx data store

    .urls
        When generating .html, this class is used to consruct URLs to related pages. By default,
        it uses dfx_html.UrlMaker.

    ._url_prefix
        If you want the hyperlinks in .html to start with something, set this. For example,
        by default a hyperlink might be '/column/city', but if you wanted the hyperlink to be
        '/mydata/dataset1/column/city', you would set ._url_prefix to '/mydata/dataset1' before
        calling .html

    ._calculate(), and design desision regarding properties
        Good python generally prescibes that methods (function calls) should do
        the heavy work and properties should return simple values. Describer classes
        diverge slightly from this.

        AbstractDescriber classes follow a pattern of having many properties, which are available
        once a heavy calculate() method has been called once. A call to any property will
        check that a calculate() has been completed, and call calculate() if not. So the
        first call to a property will be heavy (which is not pythonic), but then all
        subsequent calls to any property will be quick (which is pythonic).

    """

    # hash properties
    _hash = None
    _hash_df = None
    _hash_args = None

    # calculation properties
    _state = State.UNCALCULATED
    _description = None
    _html = None

    # url properties
    urls = dfx_html.UrlMaker()
    _url_prefix = ''

    def __init__(self, df):
        """Expected to be overriden by subclasses

        Example that still only takes a single dataframe argument
          d = ShapeRows(df)

        Example that also requires a column name argument:
          d = ColumnDescriber(df, col_name)

        """
        self.df = df
        self._set_hash()

    def __str__(self):
        return "{}, {}, {}".format(self.hash, self._state.name, self.description)

    def _set_hash(self, *args):
        """Construct a hash so that DataStore can identify this instance.
        """
        if self.df is None:
            raise ValueError("df is None")
        self._hash_df = get_df_hash(self.df)
        self._hash_args = ", ".join([str(arg) for arg in args])
        self._hash="{klass:}({df_hash:}, {args_hash:})".format(
            klass = self.__class__.__name__,
            df_hash = self._hash_df,
            args_hash = self._hash_args,
            )

    @property
    def hash(self):
        """A hash specifically designed for the dfx key-value store
        
        Expected to be set by __init__ in the implementing subclass
        """
        return self._hash

    @property
    def valid(self):
        self._ensure_calculated()
        return self._state > State.INVALID

    @property
    def qualified(self):
        self._ensure_calculated()
        return self._state > State.UNQUALIFIED

    @property
    def description(self):
        self._ensure_calculated()
        return self._description

    @property
    def html(self):
        self._ensure_calculated()
        if self._html is None:
            return self._description
        html = self._html.replace(dfx_html._URL_PREFIX, self._url_prefix)
        return html

    def _ensure_calculated(self):
        """When called the first time, run _calculate(), otherwise skip

        """
        # return immediately if already done
        if self._state > State.UNCALCULATED:
            return

        # do the actual calculation, which must be implemented by the subclass
        # but first, set default state that we expect unless the implementing class overrides
        self._state  = State.QUALIFIED        
        self._calculate()

    def _calculate(self):
        """A method intended to be run once, to calculate relevant values for .description and .html,
        and other properties.

        This isn't intended to be called by the user, but will be run a single time once the user requests
        a property that requires _calculate() to be run, such as .html

        Expection:
          # do something with df
          self._is_valid     = # determined based on data. If False, subsequent values possible, but not expected.
          self._is_qualified = # determined based on data
          self._description  = # determined based on data
          self._html         = # determined based on data
        """
        raise NotYetImplemented()

    def suppresses(self, other_describer):
        """Returns true if the other_describer doesn't provide any additional information

        To be implemented by the subclasses
        """
        return False


# #######################################################################################
# Basics

class ShapeColumns(Describer):
    def _calculate(self):
        col_count = self.df.shape[1]
        cols = [ self.urls.column(col) for col in self.df.columns ]
        self._description = '{} columns: {}'.format(col_count, ", ".join(cols))

    _qualified_dfs = [
        ('All dfs are qualified', pd.DataFrame(dict(id=['1', '2', '3'], val=[10, 20, 30])))
        ]
    _unqualified_dfs = []


class ShapeRows(Describer):
    def _calculate(self):
        self._description = '{} rows'.format(self.df.shape[0])

    _qualified_dfs = [
        ('All dfs are qualified', pd.DataFrame(dict(id=['1', '2', '3'], val=[10, 20, 30])))
        ]
    _unqualified_dfs = []

# #######################################################################################
# Columns

class ColumnDescriber(Describer):
    def __init__(self, df, col_name):
        if df is None:
            raise ValueError('df is None')
        if col_name is None:
            raise ValueError('col_name is None')
        if col_name not in df.columns:
            raise ValueError('col_name not in columnes', col_name, df.columns)
        self.df = df
        self._set_hash(col_name)
        self.col_name = col_name

class ColumnId(ColumnDescriber):
    """
    Valid     - always
    Qualified - Unique, integer

    Also mentions if is consecutive and non-null
    """

    _qualified_dfs = [
        ('consecutive', pd.DataFrame(dict(id=[1, 2, 3]))),
        ('non-consecutive', pd.DataFrame(dict(id=[1, 2, 4]))),
        ]
    _unqualified_dfs = [
        ('non-numeric', pd.DataFrame(dict(id=['1', '2', '3']))),
        ('non-unique', pd.DataFrame(dict(id=[1, 1, 2]))),
        ]

    def _calculate(self):
        col = self.df[self.col_name]
        self._is_integer = (col.dtypes == 'int64')
        self._is_unique = not (col.duplicated().any())
        if not (self._is_integer & self._is_unique):
            self._state = State.UNQUALIFIED
            if not self._is_integer:
                self._description = "Not an integer"
            elif not self._is_unique:
                self._description = "Not unique"
            return

        # if qualified
        self._description = "Unique integer"

        self._is_consecutive = (col.diff()[1:]==1).all()
        self._description += ", consecutive" if self._is_consecutive else ", non-consecutive"

        self._min = col.min()
        self._max = col.max()
        self._description += ", {}-{}".format(self._min, self._max)

    def suppresses(self, other_describer):
        if not self.qualified:
            return False
        try:
            # don't suppress if not same df and column
            if self.col_name != other_describer.col_name:
                return False
            if not self.df.equals(other_describer.df):
                return False

            # suppresses Numeric
            if other_describer.__class__ == ColumnNumeric:
                return True
            if other_describer.__class__ == ColumnUnique:
                return True
        except StandardError:
            return False

        return False

class ColumnText(ColumnDescriber):
    _qualified_dfs = [
        ('text', pd.DataFrame(dict(val=['abc', 'def', 'xyz'])))
        ]
    _unqualified_dfs = [
        ('some numeric', pd.DataFrame(dict(val=['abc', 20, 30])))
        ]

    def _calculate(self):
        col = self.df[self.col_name]
        non_str_types = [str(val_type) for val_type in list(col.apply(type).unique()) if val_type not in [str, unicode]]
        if non_str_types:
            self._description = "Non string types: {}".format(", ".join(non_str_types))
            self._state = State.UNQUALIFIED
            return

        values = col.unique()
        value_list = ", ".join(values)
        # Truncate to 100 character list
        if len(value_list) > 100:
            value_list = value_list[:100] + " [truncated...]"
        self._description = 'Text ({})'.format(value_list)

DUPLICATION_THRESHOLD = 0.2

class ColumnDuplicated(ColumnDescriber):
    """Qualifie if values are duplicated at rate above specified threshold (e.g. 20%)
    """
    _qualified_dfs = [
        ('repeated values', pd.DataFrame(dict(val=[1, 1, 3])))
        ]
    _unqualified_dfs = [
        ('unique values', pd.DataFrame(dict(val=[1, 2, 3])))
        ]

    def _calculate(self):
        self._duplicate_rate = self.df[self.col_name].duplicated().mean()
        if self._duplicate_rate < DUPLICATION_THRESHOLD:
            self._state = State.UNQUALIFIED
            self._description = 'Duplication rate {:.1%} is below threshold {:.1%}'.format(self._duplicate_rate, DUPLICATION_THRESHOLD)
            return

        self._description = 'Duplicated ({:.1%})'.format(self._duplicate_rate)

class ColumnNumeric(ColumnDescriber):
    """Qualified if col dtype is numeric
    """
    _qualified_dfs = [
        ('integers', pd.DataFrame(dict(val=[1, 2, 3]))),
        ('float', pd.DataFrame(dict(val=[1.1, 2.1, 3.1]))),
        ('mixed', pd.DataFrame(dict(val=[1, 2.1, None]))),
        ]
    _unqualified_dfs = [
        ('has text', pd.DataFrame(dict(val=[1, 2, 'abc']))),
        ('strings of numbers', pd.DataFrame(dict(val=['1', '2', '3']))),
        ]

    def _calculate(self):
        col = self.df[self.col_name]
        self._is_numeric = np.issubdtype(col.dtype, np.number)

        if not self._is_numeric:
            self._state = State.UNQUALIFIED
            self._description = "Non-numeric type: {}".format(col.dtype)
            return

        self._min = col.min()
        self._max = col.max()
        self._description = 'Numeric ({}-{})'.format(self._min, self._max)

        # histogram
        import matplotlib.pyplot as plt
        try:
            f = plt.figure()
            plt.hist(col)
            image_path, image_url = propose_image_path()
            plt.savefig(image_path)

            self._html = """
                <p>{}</p>
                <img src="{}">
                """.format(self._description, image_url)
        except StandardError as e:
            self._html = """
                <p>{}</p>
                <pre>{}</pre>
                """.format(self._description, e)


class ColumnNull(ColumnDescriber):
    """Qualified if no nulls
    """
    _qualified_dfs = [('no nulls', pd.DataFrame(dict(val=[10, 20, 30])))]
    _unqualified_dfs = [('one null', pd.DataFrame(dict(val=[10, None, 30])))]

    def _calculate(self):
        self._null_rate = self.df[self.col_name].isnull().mean()
        self._null_count = self.df[self.col_name].isnull().sum()
        if self._null_rate == 0:
            self._description = "No nulls"
        else:
            self._description = '{:.1%} nulls ({})'.format(self._null_rate, self._null_count)
            self._state = State.UNQUALIFIED

class ColumnUnique(ColumnDescriber):
    """Qualified if no values are repeated
    """

    _qualified_dfs = [('all unique', pd.DataFrame(dict(val=[10, 20, 30])))]
    _unqualified_dfs = [('repeated value', pd.DataFrame(dict(val=[10, 10, 30])))]

    def _calculate(self):
        self._duplicate_rate = self.df[self.col_name].duplicated().mean()
        if self._duplicate_rate == 0:
            self._description = 'Unique'
        else:
            self._description = "{:.1%} duplicated".format(self._duplicate_rate)
            self._state = State.UNQUALIFIED

COLUMN_CLASSES = [ColumnId, ColumnText, ColumnNumeric, ColumnNull, ColumnUnique, ColumnDuplicated]

class ColumnPageDescriber(ColumnDescriber):
    _qualified_dfs = [
        ('consecutive id', pd.DataFrame(dict(id=[1, 2, 3]))),
        ('non-consecutive id', pd.DataFrame(dict(id=[1, 2, 4]))),
        ('text', pd.DataFrame(dict(val=['abc', 'def', 'xyz']))),
        ('repeated values', pd.DataFrame(dict(val=[1, 1, 3]))),
        ('integers', pd.DataFrame(dict(val=[1, 2, 3]))),
        ('float', pd.DataFrame(dict(val=[1.1, 2.1, 3.1]))),
        ('mixed numeric', pd.DataFrame(dict(val=[1, 2.1, None]))),
        ('no nulls', pd.DataFrame(dict(val=[10, 20, 30]))),
        ('all unique', pd.DataFrame(dict(val=[10, 20, 30]))),
        ]
    _unqualified_dfs = []

    def _calculate(self):

        self._description = "(see html)"

        # sample rows
        col_index = list(self.df.columns).index(self.col_name)
        col_index_min = max(col_index-5, 0)
        col_index_max = min(col_index+5, len(self.df.columns))
        self._sample_df_html = dfx_html.df_to_html_column_highlighted(
            self.df.ix[0:5, col_index_min:col_index_max],
            self.col_name,
            self.urls,
            )

        # column description
        self._descriptions = []
        for describer_class in COLUMN_CLASSES:
            describer = factory.get_or_create(describer_class, self.df, self.col_name)
            if describer.qualified:
                self._descriptions.append(describer.html)

        # unique values
        x = self.df[self.col_name].value_counts().to_frame().reset_index()
        x.columns = ['value', 'value count']
        self._unique_values_df_html = dfx_html.df_to_html_value_counts(
            x.head(),
            self.col_name,
            self.urls
            )

        # relationships
        self.relationships = []
        for col_2_name in self.df.columns:
            if col_2_name == self.col_name:
                continue
            for relationship_class in RELATIONSHIP_CLASSES:
                relationship = factory.get_or_create(relationship_class, self.df, self.col_name, col_2_name)
                if relationship.qualified:
                    self.relationships.append(
                        (
                            self.urls.relationship(self.col_name, col_2_name),
                            relationship.description
                            ))

        # html
        template = jinja_env.get_template('column.html')
        self._html = template.render(d=self)


# #######################################################################################
# Relationship

class RelationshipDescriber(Describer):
    def __init__(self, df, col_1_name, col_2_name):
        if df is None:
            raise ValueError('df is None')
        if col_1_name is None:
            raise ValueError('col_1_name is None')
        if col_2_name is None:
            raise ValueError('col_2_name is None')

        self.df = df
        self._set_hash(col_1_name, col_2_name)
        self.col_1_name = col_1_name
        self.col_2_name = col_2_name

class RelationshipAnova(RelationshipDescriber):
    """Expects first column to be group name, second column to be numeric
    """
    _qualified_dfs = [
        ('different means', pd.DataFrame(dict(group=['a', 'a', 'a', 'b', 'b', 'b'], val=[10, 20, 30, 100, 110, 120]))),
        ]
    _unqualified_dfs = [
        ('overlapping means', pd.DataFrame(dict(group=['a', 'a', 'a', 'b', 'b', 'b'], val=[10, 20, 30, 11, 21, 31]))),
        ]
    f = None
    p = None
    def _calculate(self):
        col_group = self.df[self.col_1_name]
        col_values = self.df[self.col_2_name]        

        # valid
        if not is_text(col_group):
            self._description = "{} is not text".format(self.col_1_name)
            self._state = State.INVALID
            return
        if not is_numeric(col_values):
            self._description = "{} is not numeric".format(self.col_1_name)
            self._state = State.INVALID
            return
        
        # ANOVA
        group_labels = col_group.unique()
        group_values = [list(col_values[col_group==group_name]) for group_name in group_labels]
        from scipy import stats
        try:
            self.f, self.p = stats.f_oneway(*group_values)
        except StandardError as e:
            self._description = e[0]
            self._state = State.INVALID
            return

        # qualified
        if self.p < .05:
            self._description = "{} predicts {} means".format(self.col_1_name, self.col_2_name)
        else:
            self._description = "{} does not predict {} means (p={:.1})".format(self.col_1_name, self.col_2_name, self.p)
            self._state = State.UNQUALIFIED
            return

        # html
        html = []
        html.append("<p>ANOVA F={:.2}, p={:.2}</p>".format(self.f, self.p))
        html.append(dfx_html.df_to_html_value_counts(
            self.df.groupby(self.col_1_name)[self.col_2_name].mean().to_frame().reset_index(),
            self.col_1_name,
            self.urls,
            ))
        self._html = "\n".join(html)

class RelationshipCorrelation(RelationshipDescriber):
    """Both columns must be numeric
    """
    _qualified_dfs = [
        ('linear increase', pd.DataFrame(dict(x=range(10, 15), y=range(20, 25)))),
        ]
    _unqualified_dfs = [
        ('random', pd.DataFrame(dict(x=[1, 5, 2, 4, 3], y=[1, 2, 3, 4, 5]))),
        ]
    r = None
    p = None
    def _calculate(self):
        x = self.df[self.col_1_name]
        y = self.df[self.col_2_name]        

        # valid
        if not is_numeric(x):
            self._description = "{} is not numeric".format(self.col_1_name)
            self._state = State.INVALID
            return
        if not is_numeric(y):
            self._description = "{} is not numeric".format(self.col_2_name)
            self._state = State.INVALID
            return
        
        # Correlation
        from scipy import stats
        try:
            self.r, self.p = stats.pearsonr(x, y)
        except StandardError as e:
            self._description = e[0]
            self._state = State.INVALID
            return

        # determine if qualified
        if self.p < .05:
            self._description = "{} and {} are correlated (r={:.1}, p={:.1})".format(self.col_1_name, self.col_2_name, self.r, self.p)
        else:
            self._description = "{} and {} are not correlated (p={:.1})".format(self.col_1_name, self.col_2_name, self.p)
            self._state = State.UNQUALIFIED
            return

        # only continuing here if qualified

        # regression, to plot best fit line
        import statsmodels.api
        import numpy as np
        regression = statsmodels.api.OLS(y,statsmodels.api.add_constant(x)).fit()
        constant, slope = regression.params
        x_fit = np.linspace(x.min(), x.max(), 100)
        y_fit = x_fit*slope + constant

        # scatter plot with fit line
        import matplotlib.pyplot as plt
        f = plt.figure()
        plt.scatter(x, y)
        plt.plot(x_fit, y_fit)
        image_path, image_url = propose_image_path()
        plt.savefig(image_path)
        

        # html
        self._html = """
            <p>Pearon's correlation r={:.2}, p={:.2}</p>
            <img src='{}'>
            <pre>{}</pre>
            """.format(self.r, self.p, image_url, regression.summary())

class RelationshipOneToMany(RelationshipDescriber):
    """Qualified if columns are not many:many
    """
    _qualified_dfs = [
        ('one to many', pd.DataFrame(dict(region = ['west', 'west', 'east', 'east'], state = ['CA', 'WA', 'NC', 'NY']))),
        ('one to one', pd.DataFrame(dict(x = [1, 2, 3, 4], y = [10, 11, 12, 13]))),
        ]
    _unqualified_dfs = [
        ('many to many', pd.DataFrame(dict(first_name = ['john', 'john', 'mike', 'mike'], last_name = ['smith', 'jones', 'smith', 'jones']))),
        ]

    def _calculate(self):
        col_1 = self.df[self.col_1_name]
        col_2 = self.df[self.col_2_name]
        df = self.df        
        
        # For each col_1 value, how many col_2 values does it map to?
        col_1_to_2 = df.groupby(self.col_1_name)[self.col_2_name].nunique().max()

        # For each col_2 value, how many col_1 values does it map to?
        col_2_to_1 = df.groupby(self.col_2_name)[self.col_1_name].nunique().max()

        if col_1_to_2 == 1 and col_2_to_1 == 1:
            self._description = "{} and {} have a 1:1 mapping".format(self.col_1_name, self.col_2_name)
        elif col_1_to_2 == 1:
            self._description = "{} and {} have a 1:many mapping (1:{} max)".format(self.col_1_name, self.col_2_name, col_2_to_1)
        elif col_2_to_1 == 1:
            self._description = "{} and {} have a 1:many mapping (1:{} max)".format(self.col_2_name, self.col_1_name, col_1_to_2)
        else:
            self._description = "{} and {} have a many:many relationship ({}:{})".format(
                self.col_1_name, self.col_2_name, col_2_to_1, col_1_to_2)
            self._state = State.UNQUALIFIED


        # html
        x = df.groupby([self.col_1_name, self.col_2_name]).size().to_frame().reset_index()
        x.rename(columns = {0:'row_count'}, inplace = True)
        self._html = dfx_html.df_to_html_hierarchy(x, self.urls)

RELATIONSHIP_CLASSES = [RelationshipAnova, RelationshipCorrelation, RelationshipOneToMany]

class RelationshipPageDescriber(RelationshipDescriber):
    """For two columns, describer all relationships
    """
    _qualified_dfs = [
        ('different means', pd.DataFrame(dict(group=['a', 'a', 'a', 'b', 'b', 'b'], val=[10, 20, 30, 100, 110, 120]))),
        ('linear increase', pd.DataFrame(dict(x=range(10, 15), y=range(20, 25)))),
        ('one to many', pd.DataFrame(dict(region = ['west', 'west', 'east', 'east'], state = ['CA', 'WA', 'NC', 'NY']))),
        ('one to one', pd.DataFrame(dict(x = [1, 2, 3, 4], y = [10, 11, 12, 13]))),
        ]
    _unqualified_dfs = []
    def _calculate(self):

        self._description = "(see html)"

        # sample rows
        self._sample_df_html = dfx_html.df_to_html(self.df.ix[0:5, [self.col_1_name, self.col_2_name]], self.urls)

        # relationships
        self.relationships = []
        for relationship_class in RELATIONSHIP_CLASSES:
            relationship = factory.get_or_create(relationship_class, self.df, self.col_1_name, self.col_2_name)
            self.relationships.append(relationship)

        template = jinja_env.get_template('relationship.html')
        self._html = template.render(d=self)

# #######################################################################################
# Row Page Describer

class RowPageDescriber(Describer):
    _qualified_dfs = [
        ('', pd.DataFrame(dict(emp_id = [123, 456], name=['john', 'tom'], age=[39, 62]))),
        ]
    _unqualified_dfs = []

    def __init__(self, df, row_num):
        self.df = df
        self._set_hash(row_num)
        self.row_num = row_num
        self.row_series = df.ix[row_num, :]

    def _calculate(self):
        self._description = "(see html)"
        template = jinja_env.get_template('row.html')
        self._html = template.render(describer=self)

# #######################################################################################
# Table Page Describer

class TablePageDescriber(Describer):
    """For a dataframe, build an HTML page of all relevant describers
    """
    _qualified_dfs = [
        ('people', pd.DataFrame(dict(emp_id = [123, 456], name=['john', 'tom'], age=[39, 62]))),
        ('one to many', pd.DataFrame(dict(region = ['west', 'west', 'east', 'east'], state = ['CA', 'WA', 'NC', 'NY']))),
        ('one to one', pd.DataFrame(dict(x = [1, 2, 3, 4], y = [10, 11, 12, 13]))),
        ]
    _unqualified_dfs = []

    def _calculate(self):
        self._description = "(see html)"

        df = self.df

        # basics
        self._basics = []
        for describer_class in [ShapeColumns, ShapeRows]:
            describer = factory.get_or_create(describer_class, df)
            self._basics.append( describer.description )

        # sample rows
        self._sample_df_html = dfx_html.df_to_html(df.head(), self.urls)

        # column description
        # a list of tuples, with tuples[0]=column name and tuple[1]=list of descriptions
        self._column_descriptions = []
        for col_name in df.columns:
            qualified_column_describers = []
            col_descriptions = []
            for describer_class in COLUMN_CLASSES:
                describer = factory.get_or_create(describer_class, df, col_name)
                if describer.qualified:
                    qualified_column_describers.append(describer)
            (unsuppressed_describers, suppressed_describers) = suppression_check(qualified_column_describers)
            for describer in unsuppressed_describers:
                col_descriptions.append(describer.description)
            self._column_descriptions.append( (self.urls.column(col_name), col_descriptions) )

        # relationships
        # a list of tuples, with tuples[0]=column name, and tuples[1]=list of tuples
        #   each sub tuple[0]=2nd column name, tuple[1]=description

        # 4/25 - commented out because takes too long on real datasets
        self._relationships = []
        # columns = df.columns
        # for col_1_name in columns:
        #     rel_descriptions = []
        #     for col_2_name in columns:
        #         if col_1_name == col_2_name:
        #             continue
        #         for describer_class in RELATIONSHIP_CLASSES:
        #             describer = factory.get_or_create(describer_class, df, col_1_name, col_2_name)
        #             logger.debug("TablePageDescriber relationships - {}".format(describer))
        #             if describer.qualified:
        #                 rel_descriptions.append( (self.urls.relationship(col_1_name, col_2_name), describer.description ) )
        #     self._relationships.append( (col_1_name, rel_descriptions) )

        # html
        template = jinja_env.get_template('table.html')
        self._html = template.render(describer=self)


# #######################################################################################
# Value Page Describer

class ValuePageDescriber(Describer):
    """For a given value in a column, show sample rows, frequency, means, etc
    """
    _qualified_dfs = [
        ('one to many', pd.DataFrame(dict(region = ['west', 'west', 'east', 'east'], state = ['CA', 'WA', 'NC', 'NY']))),
        ]
    _unqualified_dfs = []
    def __init__(self, df, col_name, val):
        self.df = df
        self._set_hash(col_name, val)
        self.col_name = col_name
        self.val = val

    def _calculate(self):
        # sample rows
        # assume val is always passed as a string, so convert the column to string
        self._description = "(see html)"

        i = self.df[self.col_name].apply(str)==self.val
        self._sample_df_html = dfx_html.df_to_html(self.df.ix[i, :].head(), self.urls)

        template = jinja_env.get_template('value.html')
        self._html = template.render(describer=self)

# #######################################################################################
# Helpers

def is_numeric(col):
    return np.issubdtype(col.dtype, np.number)

def is_text(col):
    non_str_types = [val_type for val_type in list(col.apply(type).unique()) if val_type not in [str, unicode]]
    return not non_str_types

def get_df_hash(df):
    if df is None:
        raise ValueError("df was None")
    #return str(pandas.util.hash_pandas_object(df).sum())
    return '1'

def suppression_check(describers):
    """Given a list of describers, determine which ones are not suppressed by any others

    Returns tuple of describer lists:
        return (unsuppressed_describers, suppressed_describers)

    """
    suppressed_describers = []
    unsuppressed_describers = []
    
    for describer_in_question in describers:        
        is_unsuppressed = True
        for some_describer in describers:            
            if some_describer.suppresses(describer_in_question):
                is_unsuppressed = False
                suppressed_describers.append(describer_in_question)
                # print some_describer.hash, " suppresses ", describer_in_question.hash
                break
        # if we got here, describer is not suppressed
        if is_unsuppressed:
            unsuppressed_describers.append(describer_in_question)
    return (unsuppressed_describers, suppressed_describers)

def propose_image_path():
    """Returns a filename with path to which newly generated images should be saved.

    This generates random file names, to avoid file naming collisions.

    This uses _IMAGE_BASE_PATH, with the expectation that the web server will set this
    constant before any describers are generated
    """
    image_name = "image_{}.png".format(''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(8)))
    image_path = os.path.join(_IMAGE_BASE_PATH, image_name)
    image_url = '/images/' + image_name
    return image_path, image_url

