"""Database handling for dividend_calculator.

Provides a thin wrapper around SQLite with helper functions to create the
schema, insert data and run queries needed by the CLI.
"""

import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

DB_PATH = Path(__file__).resolve().parent / "dividends.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickers (
    id INTEGER PRIMARY KEY,
    symbol TEXT UNIQUE NOT NULL,
    name TEXT,
    sector TEXT,
    market_cap REAL,
    current_price REAL,
    last_updated DATE
);

CREATE TABLE IF NOT EXISTS dividends (
    id INTEGER PRIMARY KEY,
    ticker_id INTEGER NOT NULL,
    ex_date DATE NOT NULL,
    pay_date DATE,
    amount REAL NOT NULL,
    currency TEXT,
    UNIQUE(ticker_id, ex_date),
    FOREIGN KEY(ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prices (
    ticker_id INTEGER NOT NULL,
    ex_date DATE NOT NULL,
    close_price REAL NOT NULL,
    PRIMARY KEY(ticker_id, ex_date),
    FOREIGN KEY(ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS splits (
    id INTEGER PRIMARY KEY,
    ticker_id INTEGER NOT NULL,
    ex_date DATE NOT NULL,
    numerator REAL NOT NULL,
    denominator REAL NOT NULL,
    UNIQUE(ticker_id, ex_date),
    FOREIGN KEY(ticker_id) REFERENCES tickers(id) ON DELETE CASCADE
);
"""


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating it if needed."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        print(f"Error opening database at {DB_PATH}: {e}")
        raise


def init_db() -> None:
    """Create tables if they do not exist."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        # Add current_price if it doesn't exist (for existing DBs)
        try:
            conn.execute("ALTER TABLE tickers ADD COLUMN current_price REAL")
        except sqlite3.OperationalError:
            pass # Already exists
        conn.commit()
    finally:
        conn.close()


def upsert_ticker(symbol: str, name: Optional[str] = None,
                  sector: Optional[str] = None,
                  market_cap: Optional[float] = None) -> int:
    """Insert or ignore a ticker and return its id.

    If the ticker already exists the existing id is returned.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO tickers (symbol, name, sector, market_cap) VALUES (?,?,?,?)",
            (symbol, name, sector, market_cap),
        )
        # Retrieve the id (whether newly inserted or existing)
        cur.execute("SELECT id FROM tickers WHERE symbol = ?", (symbol,))
        row = cur.fetchone()
        conn.commit()
        return row["id"]
    finally:
        conn.close()


def update_ticker_timestamp(ticker_id: int, timestamp: str) -> None:
    """Set the last_updated column for a ticker."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE tickers SET last_updated = ? WHERE id = ?",
            (timestamp, ticker_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_ticker_price(ticker_id: int, price: float) -> None:
    """Set the current_price column for a ticker."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE tickers SET current_price = ? WHERE id = ?",
            (price, ticker_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_ticker_last_updated(ticker_id: int) -> Optional[str]:
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT last_updated FROM tickers WHERE id = ?", (ticker_id,)
        )
        row = cur.fetchone()
        return row["last_updated"] if row else None
    finally:
        conn.close()


def insert_dividend(ticker_id: int, ex_date: str, amount: float,
                     pay_date: Optional[str] = None,
                     currency: Optional[str] = None) -> None:
    """Insert a dividend record, ignoring duplicates."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO dividends (ticker_id, ex_date, pay_date, amount, currency) "
            "VALUES (?,?,?,?,?)",
            (ticker_id, ex_date, pay_date, amount, currency),
        )
        conn.commit()
    finally:
        conn.close()


def insert_price(ticker_id: int, ex_date: str, close_price: float) -> None:
    """Insert a price record, ignoring duplicates."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO prices (ticker_id, ex_date, close_price) VALUES (?,?,?)",
            (ticker_id, ex_date, close_price),
        )
        conn.commit()
    finally:
        conn.close()


def insert_split(ticker_id: int, ex_date: str, numerator: float, denominator: float) -> None:
    """Insert a split record, ignoring duplicates."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO splits (ticker_id, ex_date, numerator, denominator) VALUES (?,?,?,?)",
            (ticker_id, ex_date, numerator, denominator),
        )
        conn.commit()
    finally:
        conn.close()


def get_splits(ticker_id: int) -> List[sqlite3.Row]:
    """Get all splits for a ticker sorted by date."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT * FROM splits WHERE ticker_id = ? ORDER BY ex_date ASC",
            (ticker_id,)
        )
        return list(cur.fetchall())
    finally:
        conn.close()


def get_all_splits() -> List[sqlite3.Row]:
    """Get all splits for all tickers."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM splits ORDER BY ex_date ASC")
        return list(cur.fetchall())
    finally:
        conn.close()


def query_dividends(filters: str = "", params: Tuple = ()) -> List[sqlite3.Row]:
    """Run a SELECT on dividends joined with tickers and prices.

    ``filters`` should be a SQL fragment starting with ``WHERE`` or empty.
    ``params`` are the parameters for the placeholders.
    """
    sql = (
        "SELECT d.*, t.symbol, t.current_price, p.close_price "
        "FROM dividends d "
        "JOIN tickers t ON d.ticker_id = t.id "
        "LEFT JOIN prices p ON d.ticker_id = p.ticker_id AND d.ex_date = p.ex_date "
    )
    if filters:
        sql += " " + filters
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        return list(cur.fetchall())
    finally:
        conn.close()


def get_all_tickers() -> List[sqlite3.Row]:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM tickers")
        return list(cur.fetchall())
    finally:
        conn.close()

# Ensure the DB is initialised on import
init_db()
