import unittest
import os

import pandas as pd

from dfx.datastore import DfxStore
import dfx.describers

class DfxStoreTest(unittest.TestCase):

	def setUp(self):
		self.file_path = 'dfx_store_test'
		self.db = DfxStore(self.file_path, exception_if_not_exists=False)

	def tearDown(self):
		if os.path.exists(self.file_path):
			os.remove(self.file_path)

	# ###############################################################

	def test_save(self):
		x = 1
		self.db.save('x', x)

	def test_get(self):
		x = 1
		self.db.save('x', x)
		x2 = self.db.get('x')
		self.assertEqual(x, x2)

	def test_df_save(self):
		df = pd.DataFrame({'id': [1,2,3], 'val':[10, 20, 30]})
		d = dfx.describers.ShapeRows(df)
		self.db.save(d.hash, d)
		d2 = self.db.get(d.hash)
		self.assertEqual(d.hash, d2.hash)
		self.assertTrue(d.df is not None)
		self.assertTrue(d2.df is not None)
		self.assertTrue((d.df==d2.df).all().all())


		