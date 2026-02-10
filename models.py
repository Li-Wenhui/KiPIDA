from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ComponentRef:
    """Reference to a specific footprint component on the board."""
    ref_des: str
    
    def __hash__(self):
        return hash(self.ref_des)
    
    def __eq__(self, other):
        if not isinstance(other, ComponentRef):
            return False
        return self.ref_des == other.ref_des

@dataclass
class UnifiedSource:
    """
    Represents a component acting as a voltage source.
    Voltage is defined by the parent PowerRail.
    """
    component_ref: ComponentRef
    pad_names: List[str] = field(default_factory=list)

@dataclass
class UnifiedLoad:
    """
    Represents a component acting as a current load.
    distribution_mode: 'UNIFORM' divides current equally among enabled pads.
    """
    component_ref: ComponentRef
    total_current: float = 0.0
    pad_names: List[str] = field(default_factory=list)
    distribution_mode: str = "UNIFORM" 

@dataclass
class VoltageRegulator:
    """
    Represents a voltage regulator connecting two PowerRails.
    Input/Output are defined by component RefDes and specific pads.
    """
    name: str  # Name of the regulator instance (e.g. "Buck 1")
    
    input_rail_name: str
    input_ref_des: str
    input_pad_names: List[str]
    
    output_rail_name: str
    output_ref_des: str
    output_pad_names: List[str]
    
    reg_type: str = "LINEAR"  # "LINEAR" or "SWITCHING"
    efficiency: float = 0.85  # Only used if SWITCHING. 0.0-1.0

@dataclass
class PowerRail:
    """
    High-level representation of a power domain.
    """
    net_name: str
    nominal_voltage: float = 0.0
    sources: List[UnifiedSource] = field(default_factory=list)
    loads: List[UnifiedLoad] = field(default_factory=list)
    # Regulators where this rail is the INPUT
    child_regulators: List[VoltageRegulator] = field(default_factory=list)
    
    def add_source(self, source: UnifiedSource):
        self.sources.append(source)
    
    def add_load(self, load: UnifiedLoad):
        self.loads.append(load)
    
    def add_child_regulator(self, reg: VoltageRegulator):
        self.child_regulators.append(reg)

