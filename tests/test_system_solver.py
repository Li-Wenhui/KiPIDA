
import unittest
from dataclasses import dataclass, field
from typing import List

# Mock Data Structures (simplified from models.py)
@dataclass
class ComponentRef:
    ref_des: str

@dataclass
class VoltageRegulator:
    name: str # Name
    input_rail_name: str
    input_ref_des: str
    input_pad_names: List[str]
    output_rail_name: str
    output_ref_des: str
    output_pad_names: List[str]
    reg_type: str = "LINEAR" 
    efficiency: float = 0.85

@dataclass
class UnifiedSource:
    component_ref: ComponentRef
    pad_names: List[str]

@dataclass
class UnifiedLoad:
    component_ref: ComponentRef
    total_current: float
    pad_names: List[str]

@dataclass
class PowerRail:
    net_name: str
    nominal_voltage: float = 0.0
    sources: List[UnifiedSource] = field(default_factory=list)
    loads: List[UnifiedLoad] = field(default_factory=list)
    child_regulators: List[VoltageRegulator] = field(default_factory=list)
    
    def add_source(self, s): self.sources.append(s)
    def add_load(self, l): self.loads.append(l)
    def add_child_regulator(self, r): self.child_regulators.append(r)

class TestSystemLogic(unittest.TestCase):
    def setUp(self):
        self.rails = []
        
        # Setup: 10V Rail -> 5V Rail via Regulator U1
        
        self.rail_10v = PowerRail(net_name="10V", nominal_voltage=10.0)
        # 10V Source (Connector J1)
        self.rail_10v.add_source(UnifiedSource(ComponentRef("J1"), ["1"]))
        
        self.rail_5v = PowerRail(net_name="5V", nominal_voltage=5.0)
        # 5V Load (IC U2)
        self.rail_5v.add_load(UnifiedLoad(ComponentRef("U2"), total_current=1.0, pad_names=["1"]))
        
        # U1 Regulator (Linear)
        reg = VoltageRegulator(
            name="Buck 1",
            input_rail_name="10V",
            input_ref_des="U1",
            input_pad_names=["IN"],
            output_rail_name="5V",
            output_ref_des="U1",
            output_pad_names=["OUT"],
            reg_type="LINEAR"
        )
        
        # Regulator is a child of Input Rail
        self.rail_10v.add_child_regulator(reg)
        
        self.rails = [self.rail_10v, self.rail_5v]
        
    def test_topology_discovery(self):
        """Verify we can trace the system topology from rails"""
        
        # 1. Identify Input/Output relationships
        
        # Check that 5V rail is fed by U1
        fed_by = None
        for r in self.rails:
            for reg in r.child_regulators:
                if reg.output_rail_name == "5V":
                    fed_by = reg
        
        self.assertIsNotNone(fed_by)
        self.assertEqual(fed_by.name, "Buck 1")
        self.assertEqual(fed_by.input_rail_name, "10V")
        
    def test_iterative_current_calc(self):
        """
        Verify calculation of input current for regulator based on output load.
        """
        # Assume 5V rail has 1A load.
        # Regulator U1 (Linear) should draw 1A + Ioq (ignore Ioq for now) from 10V.
        
        reg_load_on_10v = 0.0
        
        # Simulate Solver Loop logic
        
        # Step 1: Solve 5V Rail
        # (Assume solve happens and we confirm 1A flows)
        current_out_5v = 0.0
        for l in self.rail_5v.loads:
            current_out_5v += l.total_current
            
        self.assertEqual(current_out_5v, 1.0)
        
        # Step 2: Calculate Input Current for U1
        reg = self.rail_10v.child_regulators[0]
        
        i_in = 0.0
        if reg.reg_type == "LINEAR":
            i_in = current_out_5v
        elif reg.reg_type == "SWITCHING":
            # Pin = Pout / eff
            p_out = current_out_5v * self.rail_5v.nominal_voltage
            p_in = p_out / reg.efficiency
            i_in = p_in / self.rail_10v.nominal_voltage
            
        self.assertEqual(i_in, 1.0) # Linear 1:1
        
        # Change to Switching
        reg.reg_type = "SWITCHING"
        reg.efficiency = 0.8
        
        # Recalc
        if reg.reg_type == "SWITCHING":
             p_out = current_out_5v * self.rail_5v.nominal_voltage # 1A * 5V = 5W
             p_in = p_out / reg.efficiency      # 5W / 0.8 = 6.25W
             i_in_switch = p_in / self.rail_10v.nominal_voltage # 6.25W / 10V = 0.625A
             
        self.assertEqual(i_in_switch, 0.625)

if __name__ == '__main__':
    unittest.main()
