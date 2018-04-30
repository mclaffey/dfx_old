"""
Tests that describers populate requried fields and have valid qualified/unqualified examples


"""


import dfx.describers

_ABSTRACT_CLASSES = [
    dfx.describers.Describer,
    dfx.describers.ColumnDescriber,
    dfx.describers.RelationshipDescriber,
    ]

def _test_describer_class(describer_class):
    class_name = describer_class.__name__
    
    # qualified
    try:
        qual_dfs = describer_class._qualified_dfs
        qual_n = len(qual_dfs)
    except AttributeError:
        qual_dfs = []
        qual_n = 'NA'
        
    # unqualified
    try:
        unqual_dfs = describer_class._unqualified_dfs
        unqual_n = len(unqual_dfs)
    except AttributeError:
        unqual_dfs = []
        unqual_n = 'NA'

    # message
    error_msg = ""  
    if qual_n == 'NA' or unqual_n == 'NA':
        error_msg = "ERROR "
    print "{:25s} - {}number of test dfx (qualified, unqualified): {}, {}".format(
        class_name, error_msg, qual_n, unqual_n)
    
    
    for qualified_expected, dfs in enumerate([unqual_dfs, qual_dfs]):
        for df_info, df in dfs:
            
            # init args
            if issubclass(describer_class, dfx.describers.ColumnDescriber):
                #print class_name, 'is subclass of', dfx.describers.ColumnPageDescriber
                init_args = [df.columns[0]]
            elif issubclass(describer_class, dfx.describers.RelationshipDescriber):
                #print class_name, 'is subclass of', dfx.describers.RelationshipDescriber
                init_args = [df.columns[0], df.columns[1]]
            elif issubclass(describer_class, dfx.describers.RowPageDescriber):
                #print class_name, 'is subclass of', dfx.describers.RelationshipDescriber
                init_args = [0]
            elif issubclass(describer_class, dfx.describers.ValuePageDescriber):
                #print class_name, 'is subclass of', dfx.describers.RelationshipDescriber
                init_args = [df.columns[0], df[df.columns[0]][0]]
            else:
                #print class_name, 'is subclass of', dfx.describers.Describer
                init_args = []
                
            #print class_name, '(', init_args, ')'
            d = describer_class(df, *init_args)
            
            # basic tests
            if not d.valid:
                print "{:25s} - FAIL not valid: {}".format(class_name, df_info)
            if not d.hash:
                print "{:25s} - FAIL no hash: {}".format(class_name, df_info)
            if not d.description:
                print "{:25s} - FAIL no description: {}".format(class_name, df_info)
            if not d.html:
                print "{:25s} - FAIL no html: {}".format(class_name, df_info)
                
            # qualified            
            if qualified_expected and not d.qualified:
                print "{:25s} - FAIL expected to be qualified: {}".format(class_name, df_info)
            if not qualified_expected and d.qualified:
                print "{:25s} - FAIL expectedly to be not qualified: {}".format(class_name, df_info)

def _crawl_describer_tests(describer_class):
    """Test specified starting class and all subclasses
    """

    # test the class, unless it is abstract
    if describer_class in _ABSTRACT_CLASSES:
        pass
    else:
        _test_describer_class(describer_class)

    # recusrive through all subclasses
    for describer_subclass in describer_class.__subclasses__():
        _crawl_describer_tests(describer_subclass)

def start():
    _crawl_describer_tests(dfx.describers.Describer)

if __name__ == '__main__':
    start()