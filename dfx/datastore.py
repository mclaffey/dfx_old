import os
import shelve
import logging

logger = logging.getLogger(__name__)

class DfxStore(object):
    """Saves python objects to disk and retrieves them based on a string key value

    Additional functionality
      - get_or_create
      - dataframe handling

    -- get_or_create

        Takes a class and instantiation arguments. If it has a saved object matching
        those, it returns that object. If it does not havea  saved object, it instantiates
        the object and returns that.

        The point is that rather than the calling code creating the object, it passes
        the arguments to this datastore, which gets if it already exists.

    -- dataframe handling

        The expectation is that many objects in this datastore will include a reference
        to the same dataframes. Rather than saving redundant copies of the dataframe with
        each object, this datastore saves a single copy of the data frame. Each time it
        saves an object with this dataframe, it strips off the reference to the dataframe.
        Each time it returns an object, it reappends this to the objectself.

    Based on python's shelve module
    """

    def __init__(self, file_path, exception_if_not_exists=False):

        if not os.path.exists(file_path):
            if exception_if_not_exists:
                raise ValueError("No file exists for path", file_path)

        self._file_path = file_path

    def _get_shelf(self, flag=None):
        """Create a connection to shelf

        This raises the custom EmptyShelfException if the caller didn't
        provide flag='c' or 'n', and the shelf hasn't yet been saved
        """
        try:
            if flag:
                return shelve.open(self._file_path, flag=flag)
            else:
                return shelve.open(self._file_path)
        except Exception as e:
            if e.args[0] == "need 'c' or 'n' flag to open new db":
                raise EmptyShelfException
            else:
                raise e

    def delete_all(self):
        """Delete all items in the shelf
        """
        logger.warn('delete_all()')
        s = self._get_shelf(flag='n')
        s.close()

    def get(self, index):
        """Retrieves an object, re-adding dataframe if applicable
        """

        logger.debug("getting %s", index)

        # open shelf in read only mode
        s = self._get_shelf(flag='r')

        try:
            value = s[index] # intentionally throws KeyError
        finally:
            s.close()

        self._restore_df(value)
        return value

    def has(self, index):
        """Check if data store has a value for the given key
        """
        # check in shelf, and return False if shelf doesn't exist
        try:
            s = self._get_shelf(flag='r')
        except EmptyShelfException:
            return False

        # if shelf existed, check keys
        return index in s.keys()

    def keys(self):
        s = self._get_shelf(flag='r')
        return s.keys()

    def save(self, index, value):
        """Save an object, removing dataframe if applicable
        """

        logger.debug("saving %s", index)

        # remove df, save it for later, and save to store
        df = self._remove_df(value)
        s = self._get_shelf(flag='c')
        try:
            s[index] = value
        finally:
            s.close()

        # restore df, so save doesn't have the side effect of stripping it
        if df is not None:
            value.df = df


    def get_or_create(self, klas, df, *args):
        """Given a class and instantiation arguments, returns a saved instance if one
        matches, or creates a new one if a saved instances does not exist.

        """
        # create a shell instance, which won't have anything calculated
        instance = klas(df, *args)
        
        # try getting an existing instance from the store
        cached = None
        try:
            cached = self.get(instance.hash)
        except EmptyShelfException:
            pass
        except KeyError:
            pass

        # if an instance existed in the store, run with that
        if cached is not None:
            logger.debug("get_or_create() - Found %s", cached.hash)
            return cached

        # we didn't get anything from the store, so we need to calculate
        logger.debug("get_or_create() - Not found, created %s", instance.hash)
        instance._ensure_calculated()

        # save to store then return it
        self.save(instance.hash, instance)
        return instance

    def _remove_df(self, x):
        """If this is an object with a dataframe attribute, remove it
        """
        # skip if not applicable
        if not hasattr(x, 'df'):
            return

        # save df to datastore if not yet there
        df_hash = x._hash_df
        if df_hash is None:
            raise ValueError("Describer did not have a df hash set", type(x))
        if not self.has(df_hash):
            self.save(df_hash, x.df)

        # remove df, but return it (used by .save())
        df = x.df
        x.df = None
        return df

    def _restore_df(self, x):
        """If this is an object with a datafram attribute, restore it
        """
        # skp if not applicable
        if not hasattr(x, 'df'):
            return

        # get df from store, add to object
        x.df = self.get(x._hash_df)

class EmptyShelfException(StandardError):
    pass


