import unittest
from dividend_calculator import utils

class TestUtils(unittest.TestCase):
    def test_dividend_yield(self):
        self.assertAlmostEqual(utils.dividend_yield(5, 100), 5.0)
        self.assertAlmostEqual(utils.dividend_yield(0, 100), 0.0)
        self.assertEqual(utils.dividend_yield(5, 0), 0.0)

    def test_cagr(self):
        # 10 to 20 in 1 year = 100% growth
        self.assertAlmostEqual(utils.cagr(10, 20, 1), 100.0)
        # 100 to 121 in 2 years = 10% CAGR
        self.assertAlmostEqual(utils.cagr(100, 121, 2), 10.0)
        self.assertEqual(utils.cagr(0, 100, 5), 0.0)
        self.assertEqual(utils.cagr(100, 200, 0), 0.0)

    def test_classify_years(self):
        totals = [10, 12, 12, 8, 0, 5]
        # Changes:
        # 10 -> 12 (Up)
        # 12 -> 12 (Stalled)
        # 12 -> 8  (Reduced)
        # 8  -> 0  (Stopped)
        # 0  -> 5  (Up)
        up, stalled, reduced, stopped = utils.classify_years(totals)
        self.assertEqual(up, 2)
        self.assertEqual(stalled, 1)
        self.assertEqual(reduced, 1)
        self.assertEqual(stopped, 1)

if __name__ == "__main__":
    unittest.main()
