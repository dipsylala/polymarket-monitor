import unittest
from unittest.mock import patch

import polygon


class WalletFirstTransactionTests(unittest.TestCase):
    @patch.object(polygon, "_get", return_value=None)
    def test_failed_lookup_is_unknown(self, _get):
        self.assertIsNone(polygon.get_wallet_first_tx("0xwallet"))

    @patch.object(
        polygon,
        "_get",
        return_value={
            "status": "0",
            "message": "No transactions found",
            "result": [],
        },
    )
    def test_confirmed_empty_history_uses_zero_sentinel(self, _get):
        self.assertEqual(0, polygon.get_wallet_first_tx("0xwallet"))


if __name__ == "__main__":
    unittest.main()
