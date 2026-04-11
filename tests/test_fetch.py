import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from dividend_calculator import fetch


class FakeResponse:
    def __init__(self, *, content=b"", json_data=None):
        self.content = content
        self._json_data = json_data or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._json_data


class FakeTicker:
    def __init__(self, info, income_df, balance_df, cashflow_df):
        self.info = info
        self._income_df = income_df
        self._balance_df = balance_df
        self._cashflow_df = cashflow_df

    def get_income_stmt(self, freq="yearly"):
        return self._income_df

    def get_balance_sheet(self, freq="yearly"):
        return self._balance_df

    def get_cashflow(self, freq="yearly"):
        return self._cashflow_df


class TestFetch(unittest.TestCase):
    @patch("dividend_calculator.fetch.time.sleep", return_value=None)
    @patch("dividend_calculator.fetch._yahoo_symbol_supported", return_value=False)
    @patch("dividend_calculator.fetch.requests.get")
    @patch("dividend_calculator.fetch.db.update_ticker_face_value")
    @patch("dividend_calculator.fetch.db.get_all_tickers", return_value=[])
    @patch("dividend_calculator.fetch.db.upsert_ticker", side_effect=[1, 2])
    def test_download_nse_tickers_stores_face_value(
        self,
        upsert_ticker,
        get_all_tickers,
        update_face_value,
        mock_get,
        yahoo_supported,
        _sleep,
    ):
        main_csv_text = (
            "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "ABC,ABC Ltd,EQ,01-JAN-2020,10,1,INE000000000,10\n"
            "XYZ,XYZ Ltd,BE,01-JAN-2020,5,1,INE000000001,5\n"
        )
        empty_note_csv = (
            "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "Note: sample,,,,,,\n"
        )

        def side_effect(url, *args, **kwargs):
            if url == fetch.NSE_CSV_URL:
                return FakeResponse(content=main_csv_text.encode("utf-8"))
            if url in (fetch.NSE_INVIT_CSV_URL, fetch.NSE_REIT_CSV_URL, fetch.NSE_SME_CSV_URL):
                return FakeResponse(content=empty_note_csv.encode("utf-8"))
            return FakeResponse(json_data={})

        mock_get.side_effect = side_effect

        added = fetch.download_nse_tickers()

        self.assertEqual(added, 2)
        self.assertEqual(upsert_ticker.call_args_list[0].args[0], "ABC.NS")
        self.assertEqual(upsert_ticker.call_args_list[1].args[0], "XYZ.NS")
        self.assertEqual(update_face_value.call_args_list[0].args, (1, 10.0))
        self.assertEqual(update_face_value.call_args_list[1].args, (2, 5.0))

    @patch("dividend_calculator.fetch.time.sleep", return_value=None)
    @patch("dividend_calculator.fetch._yahoo_symbol_supported")
    @patch("dividend_calculator.fetch.requests.get")
    @patch("dividend_calculator.fetch.db.update_ticker_face_value")
    @patch("dividend_calculator.fetch.db.get_all_tickers", return_value=[])
    @patch("dividend_calculator.fetch.db.upsert_ticker", side_effect=[1, 2, 3, 4])
    def test_download_nse_tickers_adds_validated_sme_and_reit_invit_rows(
        self,
        upsert_ticker,
        _get_all_tickers,
        update_face_value,
        mock_get,
        yahoo_supported,
        _sleep,
    ):
        main_csv_text = (
            "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "ABC,ABC Ltd,EQ,01-JAN-2020,10,1,INE000000000,10\n"
        )
        sme_csv_text = (
            "SYMBOL,NAME_OF_COMPANY,SERIES,DATE_OF_LISTING,PAID_UP_VALUE,ISIN_NUMBER,FACE_VALUE\n"
            "SME1,SME One Limited,SM,01-Jan-2024,10,INE000000010,10\n"
            "SME2-RE,SME Rights Entitlement,ST,02-Jan-2024,10,INE000000011,10\n"
            "SME3,SME Three Limited,SM,03-Jan-2024,10,INE000000012,10\n"
        )
        invit_csv_text = (
            "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "INDIGRID,India Grid Trust,IV,06-Jun-17,100,5103,INE219X23014,100\n"
        )
        reit_csv_text = (
            "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE\n"
            "EMBASSY,Embassy Office Parks REIT,RR,01-Apr-19,300,400,INE041025011,300\n"
        )

        def side_effect(url, *args, **kwargs):
            if url == fetch.NSE_CSV_URL:
                return FakeResponse(content=main_csv_text.encode("utf-8"))
            if url == fetch.NSE_SME_CSV_URL:
                return FakeResponse(content=sme_csv_text.encode("utf-8"))
            if url == fetch.NSE_INVIT_CSV_URL:
                return FakeResponse(content=invit_csv_text.encode("utf-8"))
            if url == fetch.NSE_REIT_CSV_URL:
                return FakeResponse(content=reit_csv_text.encode("utf-8"))
            return FakeResponse(json_data={})

        def yahoo_side_effect(symbol):
            return symbol in {"SME1.NS"}

        mock_get.side_effect = side_effect
        yahoo_supported.side_effect = yahoo_side_effect

        added = fetch.download_nse_tickers()

        self.assertEqual(added, 4)
        self.assertEqual(
            [call.args[0] for call in upsert_ticker.call_args_list],
            ["ABC.NS", "INDIGRID.NS", "EMBASSY.NS", "SME1.NS"],
        )
        self.assertEqual(update_face_value.call_args_list[0].args, (1, 10.0))
        self.assertEqual(update_face_value.call_args_list[1].args, (2, 100.0))
        self.assertEqual(update_face_value.call_args_list[2].args, (3, 300.0))
        self.assertEqual(update_face_value.call_args_list[3].args, (4, 10.0))

    @patch("dividend_calculator.fetch.time.sleep", return_value=None)
    @patch("dividend_calculator.fetch.db.get_ticker_face_value", return_value=5.0)
    @patch("dividend_calculator.fetch.db.upsert_screener_yearly")
    @patch("dividend_calculator.fetch.db.upsert_screener_latest")
    @patch("dividend_calculator.fetch.yf.Ticker")
    def test_fetch_fundamentals_computes_metrics_and_yearly_data(
        self,
        ticker_ctor,
        upsert_latest,
        upsert_yearly,
        get_face_value,
        _sleep,
    ):
        cols = [pd.Timestamp("2025-03-31"), pd.Timestamp("2024-03-31")]
        income_df = pd.DataFrame(
            {
                cols[0]: [200.0, 10.0, 50.0],
                cols[1]: [100.0, 5.0, 25.0],
            },
            index=["NetIncome", "DilutedEPS", "EBIT"],
        )
        balance_df = pd.DataFrame(
            {
                cols[0]: [1000.0, 200.0, 1500.0, 1000.0],
                cols[1]: [800.0, 150.0, 1200.0, 1000.0],
            },
            index=["StockholdersEquity", "CurrentLiabilities", "TotalAssets", "OrdinarySharesNumber"],
        )
        cashflow_df = pd.DataFrame(
            {
                cols[0]: [-30.0],
                cols[1]: [-20.0],
            },
            index=["CashDividendsPaid"],
        )

        info = {
            "payoutRatio": None,
            "dividendYield": None,
            "trailingPE": None,
            "returnOnEquity": None,
            "bookValue": None,
            "trailingEps": None,
            "marketCap": None,
            "currentPrice": 100.0,
            "dividendRate": 5.0,
            "sharesOutstanding": 1000.0,
        }
        ticker_ctor.return_value = FakeTicker(info, income_df, balance_df, cashflow_df)

        result = fetch.fetch_fundamentals("ITC.NS", 101)

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["payout_ratio"], 15.0)
        self.assertAlmostEqual(result["dividend_yield"], 5.0)
        self.assertAlmostEqual(result["pe_ratio"], 10.0)
        self.assertAlmostEqual(result["roe"], 20.0)
        self.assertAlmostEqual(result["roce"], 50.0 / 1300.0 * 100.0)
        self.assertAlmostEqual(result["book_value"], 1.0)
        self.assertAlmostEqual(result["eps"], 10.0)
        self.assertAlmostEqual(result["market_cap_cr"], 0.01)
        self.assertEqual(result["face_value"], 5.0)

        upsert_latest.assert_called_once()
        latest_payload = upsert_latest.call_args.args[1]
        self.assertAlmostEqual(latest_payload["payout_ratio"], 15.0)
        self.assertAlmostEqual(latest_payload["dividend_yield"], 5.0)
        self.assertAlmostEqual(latest_payload["pe_ratio"], 10.0)
        self.assertAlmostEqual(latest_payload["roe"], 20.0)
        self.assertAlmostEqual(latest_payload["roce"], 50.0 / 1300.0 * 100.0)
        self.assertAlmostEqual(latest_payload["book_value"], 1.0)
        self.assertAlmostEqual(latest_payload["eps"], 10.0)
        self.assertAlmostEqual(latest_payload["market_cap_cr"], 0.01)
        self.assertEqual(latest_payload["face_value"], 5.0)
        self.assertIn("last_updated", latest_payload)

        self.assertEqual(upsert_yearly.call_count, 2)
        first_year = upsert_yearly.call_args_list[0].args
        second_year = upsert_yearly.call_args_list[1].args
        self.assertEqual(first_year[0], 101)
        self.assertEqual(first_year[1], "Mar 2025")
        self.assertEqual(second_year[1], "Mar 2024")
        self.assertAlmostEqual(first_year[2]["payout_ratio"], 15.0)
        self.assertAlmostEqual(first_year[2]["roe"], 20.0)
        self.assertAlmostEqual(second_year[2]["payout_ratio"], 20.0)
        self.assertAlmostEqual(second_year[2]["roe"], 12.5)


if __name__ == "__main__":
    unittest.main()
