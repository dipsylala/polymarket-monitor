import unittest
from unittest.mock import Mock, patch

import requests

import polymarket


class RecentTradesTests(unittest.TestCase):
    def _response(self, payload, status_code=200):
        response = Mock()
        response.status_code = status_code
        response.text = ""
        response.json.return_value = payload
        response.raise_for_status.side_effect = (
            requests.HTTPError(f"HTTP {status_code}", response=response)
            if status_code >= 400
            else None
        )
        return response

    @patch.object(polymarket.time, "sleep")
    @patch.object(polymarket._SESSION, "get")
    def test_queries_each_market_with_server_side_filters(self, get, _sleep):
        market_a = "0x" + "a" * 64
        market_b = "0x" + "b" * 64
        get.side_effect = [
            self._response([
                {
                    "conditionId": market_a,
                    "timestamp": 200,
                    "side": "BUY",
                    "outcome": "Yes",
                    "size": 1000,
                    "price": 0.6,
                },
                {
                    "conditionId": market_a,
                    "timestamp": 90,
                    "side": "BUY",
                    "outcome": "Yes",
                    "size": 1000,
                    "price": 0.6,
                },
            ]),
            self._response([
                {
                    "conditionId": market_b,
                    "timestamp": 190,
                    "side": "BUY",
                    "outcome": "No",
                    "size": 1000,
                    "price": 0.6,
                },
                {
                    "conditionId": market_b,
                    "timestamp": 180,
                    "side": "BUY",
                    "outcome": "Yes",
                    "size": 100,
                    "price": 0.6,
                },
            ]),
        ]

        trades = polymarket.get_recent_trades({
            market_a: 100,
            market_b: 100,
        })

        self.assertEqual(1, len(trades))
        self.assertEqual(market_a, trades[0]["conditionId"])
        self.assertEqual(2, get.call_count)
        for call, market in zip(get.call_args_list, (market_a, market_b)):
            params = call.kwargs["params"]
            self.assertEqual(market, params["market"])
            self.assertEqual("false", params["takerOnly"])
            self.assertEqual("BUY", params["side"])
            self.assertEqual("CASH", params["filterType"])
            self.assertEqual(500.0, params["filterAmount"])

    @patch.object(polymarket.time, "sleep")
    @patch.object(polymarket._SESSION, "get")
    def test_raises_instead_of_returning_partial_results(self, get, _sleep):
        market = "0x" + "a" * 64
        get.return_value = self._response([], status_code=503)

        with self.assertRaises(polymarket.TradeFetchError):
            polymarket.get_recent_trades({market: 100})

        self.assertEqual(polymarket._DATA_API_MAX_ATTEMPTS, get.call_count)

    @patch.object(polymarket, "_DATA_API_MAX_OFFSET", 2)
    @patch.object(polymarket, "_DATA_API_PAGE_SIZE", 2)
    @patch.object(polymarket._SESSION, "get")
    def test_raises_when_pagination_window_is_exhausted(self, get):
        market = "0x" + "a" * 64
        full_page = [
            {
                "conditionId": market,
                "timestamp": 200,
                "side": "BUY",
                "outcome": "Yes",
                "size": 1000,
                "price": 0.6,
            },
            {
                "conditionId": market,
                "timestamp": 199,
                "side": "BUY",
                "outcome": "Yes",
                "size": 1000,
                "price": 0.6,
            },
        ]
        get.side_effect = [
            self._response(full_page),
            self._response(full_page),
        ]

        with self.assertRaises(polymarket.TradeFetchError):
            polymarket.get_recent_trades({market: 100})

        self.assertEqual(
            [0, 2],
            [call.kwargs["params"]["offset"] for call in get.call_args_list],
        )


class WalletTradeHistoryTests(unittest.TestCase):
    @patch.object(polymarket._SESSION, "get")
    def test_excludes_current_trade_from_prior_count_but_not_markets(self, get):
        address = "0xwallet"
        get.return_value = RecentTradesTests()._response([
            {"conditionId": "market-a", "transactionHash": "0xcurrent"},
        ])

        total, markets = polymarket.get_wallet_trade_history(address, exclude_tx_hash="0xcurrent")

        self.assertEqual(0, total)
        self.assertEqual(1, markets)

    @patch.object(polymarket._SESSION, "get")
    def test_counts_all_trades_when_no_exclusion_given(self, get):
        address = "0xwallet"
        get.return_value = RecentTradesTests()._response([
            {"conditionId": "market-a", "transactionHash": "0xone"},
            {"conditionId": "market-b", "transactionHash": "0xtwo"},
        ])

        total, markets = polymarket.get_wallet_trade_history(address)

        self.assertEqual(2, total)
        self.assertEqual(2, markets)


class MarketFilterTests(unittest.TestCase):
    @patch.object(polymarket._SESSION, "get")
    def test_excludes_sports_market_with_geopolitical_country_name(self, get):
        get.side_effect = [
            RecentTradesTests()._response([
                {
                    "question": "Will Iran win the 2026 FIFA World Cup?",
                    "conditionId": "sports",
                },
                {
                    "question": "Will Israel strike Iran in June?",
                    "conditionId": "geopolitical",
                },
            ]),
            RecentTradesTests()._response([]),
        ]

        markets = polymarket.get_geopolitical_markets()

        self.assertEqual(
            ["geopolitical"],
            [market["conditionId"] for market in markets],
        )


if __name__ == "__main__":
    unittest.main()
