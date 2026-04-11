import unittest
from datetime import timezone

from dividend_calculator.timeutils import parse_utc_timestamp, utc_from_timestamp, utc_now_iso


class TestTimeUtils(unittest.TestCase):
    def test_parse_utc_timestamp_upgrades_naive_values(self):
        parsed = parse_utc_timestamp("2026-04-11T12:34:56")

        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.isoformat(), "2026-04-11T12:34:56+00:00")

    def test_parse_utc_timestamp_normalizes_aware_values(self):
        parsed = parse_utc_timestamp("2026-04-11T18:04:56+05:30")

        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.isoformat(), "2026-04-11T12:34:56+00:00")

    def test_utc_helpers_return_aware_values(self):
        now_iso = utc_now_iso()
        parsed_now = parse_utc_timestamp(now_iso)
        from_ts = utc_from_timestamp(0)

        self.assertEqual(parsed_now.tzinfo, timezone.utc)
        self.assertEqual(from_ts.isoformat(), "1970-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
