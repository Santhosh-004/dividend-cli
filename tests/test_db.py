import unittest
from unittest.mock import MagicMock, patch

from dividend_calculator import db


class TestDbHelpers(unittest.TestCase):
    @patch("dividend_calculator.db.get_connection")
    def test_get_ticker_face_value(self, get_connection):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"face_value": 10.0}
        get_connection.return_value = conn

        self.assertEqual(db.get_ticker_face_value(1), 10.0)

    @patch("dividend_calculator.db.get_connection")
    def test_update_ticker_face_value(self, get_connection):
        conn = MagicMock()
        get_connection.return_value = conn

        db.update_ticker_face_value(7, 5.0)

        conn.execute.assert_called_once_with(
            "UPDATE tickers SET face_value = ? WHERE id = ?",
            (5.0, 7),
        )
        conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
