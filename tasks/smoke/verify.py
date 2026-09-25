"""Kept on host during agent execution; copied to a fresh verifier container later."""
import unittest
from ranges import inclusive_range


class HiddenTests(unittest.TestCase):
    def test_cases(self):
        for start, stop, expected in [
            (2, 4, [2, 3, 4]), (3, 1, [3, 2, 1]), (0, 0, [0]),
            (-3, -1, [-3, -2, -1]), (1, -2, [1, 0, -1, -2]),
            (-2, -4, [-2, -3, -4]),
        ]:
            with self.subTest(start=start, stop=stop):
                self.assertEqual(inclusive_range(start, stop), expected)


if __name__ == '__main__':
    unittest.main()
