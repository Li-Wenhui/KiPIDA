
import matplotlib
# Use Agg backend to avoid GUI requirement for matplotlib, since we just want images
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import io
import wx
import numpy as np
import math

class Plotter:
    def __init__(self, debug=False):
        self.debug = debug

    def plot_3d_mesh(self, mesh, stackup=None, vmin=None, vmax=None):
        """
        Generates a 3D scatter plot of the mesh nodes.
        Returns a wx.Bitmap.
        """
        try:
            fig = plt.figure(figsize=(7, 5), constrained_layout=True)
            ax = fig.add_subplot(111, projection='3d')
            
            xs, ys, zs, c = [], [], [], []
            has_results = hasattr(mesh, 'results') and mesh.results
            
            layer_to_z = {}
            if stackup and 'layer_order' in stackup:
                for idx, layer_id in enumerate(stackup['layer_order']):
                    layer_to_z[layer_id] = 10.0 - idx
            else:
                copper_layers = sorted(stackup['copper'].keys()) if stackup and 'copper' in stackup else []
                for idx, layer_id in enumerate(copper_layers):
                    layer_to_z[layer_id] = 10.0 - idx
            
            # If no node_coords populated yet (edge case), return None
            if not mesh.node_coords:
                plt.close(fig)
                return None

            for nid, (x, y, layer) in mesh.node_coords.items():
                xs.append(x)
                ys.append(-y)  # Invert Y to match KiCad
                zs.append(layer_to_z.get(layer, 10 - layer * 0.5))
                c.append(mesh.results.get(nid, 0.0) if has_results else layer)
                
            sc = ax.scatter(xs, ys, zs, c=c, cmap='viridis', vmin=vmin, vmax=vmax)
            if has_results:
                plt.colorbar(sc, label='Voltage (V)', shrink=0.8)
            
            ax.set_xlabel('X (mm)'); ax.set_ylabel('Y (mm)'); ax.set_zlabel('L (pseudo)')
            
            # Equal aspect ratio
            x_limits = ax.get_xlim3d()
            y_limits = ax.get_ylim3d()
            x_range = x_limits[1] - x_limits[0]
            y_range = y_limits[1] - y_limits[0]
            max_range = max(x_range, y_range)
            x_mid = (x_limits[0] + x_limits[1]) / 2.0
            y_mid = (y_limits[0] + y_limits[1]) / 2.0
            ax.set_xlim3d([x_mid - max_range/2, x_mid + max_range/2])
            ax.set_ylim3d([y_mid - max_range/2, y_mid + max_range/2])
            
            return self._fig_to_bitmap(fig)
        except Exception as e:
            if self.debug: print(f"Plotter 3D Error: {e}")
            return None

    def plot_layer_2d(self, mesh, layer_id, stackup=None, vmin=None, vmax=None, layer_name=None):
        """
        Generates a 2D plot (heatmap) for a specific layer.
        Returns a wx.Bitmap.
        """
        try:
            fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
            
            xs, ys, vs = [], [], []
            has_results = hasattr(mesh, 'results') and mesh.results
            
            # Filter nodes for this layer
            nodes_on_layer = [nid for nid in mesh.nodes if mesh.node_coords[nid][2] == layer_id]
            
            if not nodes_on_layer:
                plt.close(fig)
                return None

            for nid in nodes_on_layer:
                coords = mesh.node_coords[nid]
                xs.append(coords[0])
                ys.append(-coords[1]) # Invert Y
                val = mesh.results.get(nid, 0.0) if has_results else 0.0
                vs.append(val)
                
            if not xs:
                plt.close(fig)
                return None

            # Scatter plot for now - tripcolor or imshow is better if we have regular grid, 
            # but scatter is robust for sparse nodes.
            # Using a fixed marker size might be tricky, let's try a reasonable default.
            # Ideally s should relate to grid_size, but scatter size is in points^2.
            # Let's just use a standard size for visibility.
            sc = ax.scatter(xs, ys, c=vs, cmap='viridis', vmin=vmin, vmax=vmax, s=20)
            
            if has_results:
                plt.colorbar(sc, label='Voltage (V)')
            
            if layer_name is None:
                layer_name = str(layer_id)
                if stackup and 'copper' in stackup and layer_id in stackup['copper']:
                     # Try to get layer name? currently stackup dict structure in test is simple
                     pass

            ax.set_title(f"Layer: {layer_name}")
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_aspect('equal', 'box')
            
            return self._fig_to_bitmap(fig)

        except Exception as e:
            if self.debug: print(f"Plotter 2D Error: {e}")
            return None

    def _fig_to_bitmap(self, fig):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        image = wx.Image(buf, wx.BITMAP_TYPE_PNG)
        return wx.Bitmap(image)

    def _calculate_current_density_map(self, mesh, stackup):
        """
        Calculates current density (A/mm^2) for each node.
        Returns dict: { node_id: current_density_float }
        """
        if not hasattr(mesh, 'results') or not mesh.results:
            return {}
        
        # Build reverse lookup if not present (mesh usually has node_map)
        # We need (x_idx, y_idx, layer) -> node_id
        # node_coords stores (x, y, layer), but not indices directly unless we infer them
        # mesh.node_map stores (xi, yi, layer) -> nid. This is what we need.
        if not hasattr(mesh, 'node_map') or not mesh.node_map:
             if self.debug: print("Plotter: Mesh has no node_map, cannot calculate gradients.")
             return {}

        density_map = {}
        rho_default = 1.7e-5 # Ohm*mm
        
        # Pre-calculate rho per layer
        layer_rho = {}
        if stackup and 'copper' in stackup:
            for lid, info in stackup['copper'].items():
                layer_rho[lid] = info.get('resistivity', rho_default)
        else:
            # Fallback
            pass 

        # Grid step
        gs = mesh.grid_step
        if gs <= 0: gs = 0.1
        
        # Iterate all nodes to calculate J vector
        for (xi, yi, layer), nid in mesh.node_map.items():
            if nid not in mesh.results: continue
            
            v_c = mesh.results[nid]
            rho = layer_rho.get(layer, rho_default)
            
            # Gradient X
            # Try Central Difference: (V(x-1) - V(x+1)) / (2*dx)
            # If boundary, use Forward/Backward
            
            # Neighbors
            n_left  = mesh.node_map.get((xi-1, yi, layer))
            n_right = mesh.node_map.get((xi+1, yi, layer))
            n_up    = mesh.node_map.get((xi, yi-1, layer)) # y-1 because y index decreases upwards usually? wait, mesh definition.
            n_down  = mesh.node_map.get((xi, yi+1, layer))
            
            # E_x = -dV/dx
            Ex = 0.0
            if n_left is not None and n_right is not None:
                if n_left in mesh.results and n_right in mesh.results:
                    # Central
                     Ex = (mesh.results[n_left] - mesh.results[n_right]) / (2*gs)
            elif n_left is not None and n_left in mesh.results:
                # Backward: (V(x-1) - V(x)) / dx
                Ex = (mesh.results[n_left] - v_c) / gs
            elif n_right is not None and n_right in mesh.results:
                # Forward: (V(x) - V(x+1)) / dx
                Ex = (v_c - mesh.results[n_right]) / gs
                
            # E_y = -dV/dy
            Ey = 0.0
            if n_up is not None and n_down is not None:
                if n_up in mesh.results and n_down in mesh.results:
                    # Central (ordering depends on axis direction, assumes y increases 'down' or 'up'. 
                    # E vector direction magnitude doesn't care about sign much for heatmap)
                     Ey = (mesh.results[n_up] - mesh.results[n_down]) / (2*gs)
            elif n_up is not None and n_up in mesh.results:
                Ey = (mesh.results[n_up] - v_c) / gs
            elif n_down is not None and n_down in mesh.results:
                Ey = (v_c - mesh.results[n_down]) / gs
                
            # J = E / rho
            J_mag = math.sqrt(Ex**2 + Ey**2) / rho
            
            # Convert to A/mm^2 (since V is Volts, gs is mm, rho is Ohm*mm)
            # Unit check: V / mm / (Ohm * mm) = A / mm^2. Correct.
            
            density_map[nid] = J_mag
            
        return density_map

    def plot_layer_current_density(self, mesh, layer_id, density_map, stackup=None, layer_name=None, vmax=None):
        """
        Generates a 2D plot (heatmap) of Current Density for a specific layer.
        Returns a wx.Bitmap.
        """
        try:
            fig, ax = plt.subplots(figsize=(7, 5), constrained_layout=True)
            
            xs, ys, js = [], [], []
            has_data = bool(density_map)
            
            # Filter nodes for this layer
            nodes_on_layer = [nid for nid in mesh.nodes if mesh.node_coords[nid][2] == layer_id]
            
            if not nodes_on_layer:
                plt.close(fig)
                return None
            
            curr_max_j = 0
            for nid in nodes_on_layer:
                coords = mesh.node_coords[nid]
                xs.append(coords[0])
                ys.append(-coords[1]) # Invert Y
                val = density_map.get(nid, 0.0)
                js.append(val)
                if val > curr_max_j: curr_max_j = val
                
            if not xs:
                plt.close(fig)
                return None
            
            # Use provided vmax if available, else auto-scale
            plot_vmax = vmax if vmax is not None else (curr_max_j if curr_max_j > 0 else 1.0)

            # Scatter plot with 'plasma' or 'inferno' for intensity
            # cmap 'plasma' is good for perceptually uniform intensity
            sc = ax.scatter(xs, ys, c=js, cmap='plasma', s=20, vmin=0, vmax=plot_vmax)
            
            if has_data:
                plt.colorbar(sc, label='Current Density ($A/mm^2$)')
            
            if layer_name is None:
                layer_name = str(layer_id)

            ax.set_title(f"Layer: {layer_name} - Current Density")
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_aspect('equal', 'box')
            
            return self._fig_to_bitmap(fig)

        except Exception as e:
            if self.debug: print(f"Plotter J Error: {e}")
            import traceback
            traceback.print_exc()
            return None
