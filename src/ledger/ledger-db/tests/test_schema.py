"""Static checks of the ledger schema (no database needed)."""
import os
import re
import unittest

SQL = os.path.join(os.path.dirname(__file__), '..', 'initdb',
                   '0_init_tables.sql')


class LedgerSchemaTest(unittest.TestCase):
    def setUp(self):
        with open(SQL) as f:
            self.sql = f.read()

    def test_category_column_defaults_to_other(self):
        self.assertRegex(
            self.sql,
            re.compile(r"CATEGORY\s+VARCHAR\(\d+\)\s+NOT NULL\s+"
                       r"DEFAULT\s+'Other'", re.I))

    def test_category_column_is_in_transactions_table(self):
        table = self.sql.split('CREATE TABLE TRANSACTIONS', 1)[1]
        table = table.split(');', 1)[0]
        self.assertIn('CATEGORY', table)


if __name__ == '__main__':
    unittest.main()
