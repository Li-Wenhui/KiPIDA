import unittest
import sys
import os

# Add parent directory to sys.path to import models
plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from models import generate_regulator_name

class TestRegulatorNaming(unittest.TestCase):
    def test_same_component(self):
        self.assertEqual(generate_regulator_name("U1", "U1"), "U1")
        self.assertEqual(generate_regulator_name("L1", "L1"), "L1")

    def test_different_components(self):
        self.assertEqual(generate_regulator_name("U1", "U2"), "U1 -> U2")
        self.assertEqual(generate_regulator_name("J1", "U5"), "J1 -> U5")

    def test_empty_inputs(self):
        self.assertEqual(generate_regulator_name("", "U1"), "U1")
        self.assertEqual(generate_regulator_name("U1", ""), "U1")
        self.assertEqual(generate_regulator_name("", ""), "")

if __name__ == "__main__":
    unittest.main()
