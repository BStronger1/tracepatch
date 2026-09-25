import unittest
from ranges import inclusive_range


class VisibleTests(unittest.TestCase):
    def test_ascending(self):
        self.assertEqual(inclusive_range(2, 4), [2, 3, 4])


if __name__ == '__main__':
    unittest.main()
