import unittest
from context import ContextPolicy, heat_index_c
from features import FeatureWindow
from test_core import reading

class ContextTests(unittest.TestCase):
    def test_five_past_readings(self):
        window = FeatureWindow()
        for index in range(5):
            features = window.push(reading(index, 20 + index, 1700000000 + index * 5))
            if index < 4:
                self.assertIsNone(features)
        self.assertEqual(features[3], 22)
        self.assertEqual(features[5], 4)

    def test_gap_resets_window(self):
        window = FeatureWindow()
        for index in range(5):
            window.push(reading(index, epoch=1700000000 + index * 5))
        self.assertIsNone(window.push(reading(6, epoch=1700000100)))

    def test_invalid_reading_resets_window(self):
        window = FeatureWindow()
        for index in range(5):
            window.push(reading(index, epoch=1700000000 + index * 5))
        self.assertIsNone(window.push(reading(6, None, 1700000030)))
        self.assertEqual(len(window.rows), 0)

    def test_hysteresis(self):
        policy, row = ContextPolicy(), reading()
        def state(t, h):
            return policy.update(row, [t, h, 1013, t, h, 0])["state"]
        self.assertEqual(state(28, 50), "attention")
        self.assertEqual(state(27, 50), "attention")
        self.assertEqual(state(26, 50), "normal")
        self.assertEqual(state(24, 75), "attention")
        self.assertEqual(state(24, 72), "attention")
        self.assertEqual(state(24, 70), "normal")

    def test_unknown_is_not_normal(self):
        row = reading(temperature=None)
        self.assertEqual(ContextPolicy().update(row, None)["state"], "unknown")

    def test_heat_index_reference_and_domain(self):
        self.assertAlmostEqual(heat_index_c(30, 70), 35.038, places=2)
        self.assertIsNone(heat_index_c(20, 50))
        self.assertIsNone(heat_index_c(30, 90))
        self.assertIsNone(heat_index_c(float("nan"), 50))

if __name__ == "__main__":
    unittest.main()