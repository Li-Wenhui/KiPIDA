
import unittest
import sys
import os

# Add plugin root to path
plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# Mock wx if strictly necessary, but let's try assuming it might be present or we can mock it
# For CI/headless correctness without wx installed, we often mock wx.
# Let's simple-mock wx to ensure logic runs even if system python doesn't have wx (though user python likely does)
import types
if 'wx' not in sys.modules:
    wx_mock = types.ModuleType('wx')
    wx_mock.Bitmap = lambda *args: "BITMAP_OBJECT"
    wx_mock.Image = lambda *args: "IMAGE_OBJECT"
    wx_mock.BITMAP_TYPE_PNG = 1
    sys.modules['wx'] = wx_mock

from plotter import Plotter
from mesh import Mesh

class TestPlotter(unittest.TestCase):
    def setUp(self):
        self.plotter = Plotter(debug=True)
        self.mesh = Mesh()
        # Create a simple dummy mesh
        # Nodes 0,1 on layer 0
        # Nodes 2,3 on layer 1
        self.mesh.nodes = [0, 1, 2, 3]
        self.mesh.node_coords = {
            0: (0.0, 0.0, 0),
            1: (1.0, 1.0, 0),
            2: (0.0, 0.0, 1),
            3: (1.0, 1.0, 1)
        }
        self.mesh.results = {
            0: 3.3,
            1: 3.2,
            2: 3.3,
            3: 3.1
        }
        self.stackup = {
            'copper': {0: {}, 1: {}},
            'layer_order': [0, 1]
        }

    def test_plot_3d(self):
        # Should return a bitmap (or mock string)
        bmp = self.plotter.plot_3d_mesh(self.mesh, self.stackup)
        print(f"3D Plot result: {bmp}")
        self.assertIsNotNone(bmp)
        
    def test_plot_2d_layer(self):
        # Should return a bitmap for layer 0
        bmp = self.plotter.plot_layer_2d(self.mesh, 0, self.stackup, vmin=3.0, vmax=3.5, layer_name="F.Cu (Test)")
        print(f"2D Plot Layer 0 result: {bmp}")
        self.assertIsNotNone(bmp)
        
    def test_plot_2d_empty_layer(self):
        # Layer 99 empty
        bmp = self.plotter.plot_layer_2d(self.mesh, 99, self.stackup)
        self.assertIsNone(bmp)

    def test_calculate_current_density(self):
        # 1. Setup Linear Mesh (2 nodes)
        self.mesh.nodes = [0, 1]
        self.mesh.node_coords = {
            0: (0.0, 0.0, 0),
            1: (0.1, 0.0, 0)
        }
        # Needed for Gradient Calc
        self.mesh.node_map = {
            (0, 0, 0): 0,
            (1, 0, 0): 1
        }
        self.mesh.grid_step = 0.1
        
        # 2. Results (V)
        # V0=1.0, V1=0.9 -> dV=0.1 over 0.1mm -> E=1.0 V/mm
        self.mesh.results = {
            0: 1.0, 
            1: 0.9
        }
        
        # 3. Stackup with known resistivity
        # rho = 0.001 Ohm*mm (dummy)
        # J = E/rho = 1.0 / 0.001 = 1000 A/mm^2
        stackup_test = {
            'copper': {
                0: {'resistivity': 0.001}
            }
        }
        
        density_map = self.plotter._calculate_current_density_map(self.mesh, stackup_test)
        
        self.assertIn(0, density_map)
        self.assertIn(1, density_map)
        
        # Check Node 0 (Forward diff likely, as left neighbor missing)
        # E = (1.0 - 0.9)/0.1 = 1.0
        # J = 1000
        self.assertAlmostEqual(density_map[0], 1000.0, places=1)
        
        # Check Node 1 (Backward diff likely)
        # E = (1.0 - 0.9)/0.1 = 1.0
        # J = 1000
        self.assertAlmostEqual(density_map[1], 1000.0, places=1)
        
    def test_calculate_current_density_2d(self):
        # 2D diagonal gradient
        # (0,0)=1.0, (1,0)=0.9, (0,1)=0.9
        # dx=0.1
        self.mesh.nodes = [0, 1, 2]
        self.mesh.node_coords = {
            0: (0.0, 0.0, 0),
            1: (0.1, 0.0, 0),
            2: (0.0, 0.1, 0)
        }
        self.mesh.node_map = {
            (0, 0, 0): 0,
            (1, 0, 0): 1,
            (0, 1, 0): 2
        }
        self.mesh.grid_step = 0.1
        self.mesh.results = {0: 1.0, 1: 0.9, 2: 0.9}
        
        rho = 1.0
        stackup = {'copper': {0: {'resistivity': rho}}}
        
        # Node 0:
        # Ex (Forward) = (1.0 - 0.9)/0.1 = 1.0
        # Ey (Forward, y-axis inverted in logic? let's check implementation again)
        # Implementation: 
        #   n_down (y+1) is node 2 (0, 0.1). 
        #   Ey = (v_c - v_down) / gs = (1.0 - 0.9)/0.1 = 1.0
        # J = sqrt(1^2 + 1^2)/1 = 1.414...
        
        density_map = self.plotter._calculate_current_density_map(self.mesh, stackup)
        self.assertAlmostEqual(density_map[0], 1.4142, places=3)

    def test_physics_validation_one_amp(self):
        """
        Validates the current density calculation against a known physics scenario.
        Scenario: 1A current flowing through a 1mm wide, 0.035mm thick copper trace.
        
        Cross-sectional Area A = 1.0 mm * 0.035 mm = 0.035 mm^2.
        Expected Current Density J = I / A = 1.0 A / 0.035 mm^2 = 28.5714 A/mm^2.
        
        We simulate a small segment of length dx = 0.1 mm.
        Resistivity rho = 1.72e-5 Ohm-mm.
        Resistance of segment R_seg = rho * L / A = 1.72e-5 * 0.1 / 0.035.
        Voltage Drop dV = I * R_seg = 1.0 * (1.72e-5 * 0.1 / 0.035).
        
        We set up two nodes at x=0 and x=0.1 with this voltage difference.
        The plotter should calculate J approx 28.57.
        """
        # Parameters
        width = 1.0 # mm
        thick = 0.035 # mm - Standard 1oz copper
        rho = 1.72e-5 # Ohm-mm
        current = 1.0 # A
        dx = 0.1 # mm
        
        # Theoretical values
        area = width * thick
        expected_J = current / area # 28.57 A/mm^2
        
        R_seg = rho * dx / area
        dV = current * R_seg
        
        # Setup Mesh
        self.mesh.nodes = [0, 1]
        self.mesh.grid_step = dx
        self.mesh.node_coords = {
            0: (0.0, 0.0, 0),
            1: (dx, 0.0, 0)
        }
        self.mesh.node_map = {
            (0, 0, 0): 0,
            (1, 0, 0): 1
        }
        
        # Set Voltages
        v_start = 1.0
        self.mesh.results = {
            0: v_start,
            1: v_start - dV
        }
        
        # Setup Stackup
        stackup = {
            'copper': {
                0: {'resistivity': rho, 'thickness': thick}
            }
        }
        
        # Calculate
        density_map = self.plotter._calculate_current_density_map(self.mesh, stackup)
        
        # Verify
        # We check both nodes. 
        # Node 0 (Forward diff): (V0 - V1)/dx = dV/dx = (I*R_seg)/dx = (I*rho/A)
        # J = E/rho = I/A
        self.assertAlmostEqual(density_map[0], expected_J, places=2, 
                               msg=f"Expected J={expected_J:.2f}, got {density_map[0]:.2f}")
        self.assertAlmostEqual(density_map[1], expected_J, places=2)
        
        print(f"\n[Physics Check] 1A in 1mm x 0.035mm trace:")
        print(f"  Expected J = {expected_J:.4f} A/mm^2")
        print(f"  Calculated J = {density_map[0]:.4f} A/mm^2")

if __name__ == '__main__':
    unittest.main()
