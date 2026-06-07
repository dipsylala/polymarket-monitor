import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database


class DatabaseMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db_path_patch = patch.object(database, "DB_PATH", self.db_path)
        self.db_path_patch.start()
        database.init_db()

    def tearDown(self):
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def test_prune_watchlist_hits_preserves_recent_rows(self):
        database.insert_watchlist_hit(
            "0xwallet",
            "old-market",
            "old-tx",
            "BUY",
            "Yes",
            10,
            0.5,
            100,
        )
        database.insert_watchlist_hit(
            "0xwallet",
            "new-market",
            "new-tx",
            "BUY",
            "Yes",
            10,
            0.5,
            200,
        )

        pruned = database.prune_watchlist_hits(150)

        self.assertEqual(1, pruned)
        self.assertFalse(database.watchlist_hit_exists("old-tx"))
        self.assertTrue(database.watchlist_hit_exists("new-tx"))

    def test_compact_skips_database_below_threshold(self):
        self.assertFalse(database.compact_if_larger_than(45))

    def test_compact_runs_above_threshold(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("CREATE TABLE padding (value BLOB)")
            conn.execute("INSERT INTO padding VALUES (zeroblob(1048576))")
            conn.commit()
        finally:
            conn.close()

        self.assertTrue(database.compact_if_larger_than(0))


if __name__ == "__main__":
    unittest.main()
