"""Çip seviyesinde gecikmeli lojik simülatör: çekirdek (kernel) + 74HC/bellek modelleri (chips).

    from td8.hw import Sim, HC161, HC245, ...
    sim = Sim(corner='max')
    sim.add(HC161('U12', {...}))
"""

from .chips import (CHIP_TYPES, DELAYS, LIMITS, Chip, CY62256, HC00, HC02, HC04, HC08, HC14,
                    HC20, HC32, HC74, HC138, HC139, HC153, HC157, HC161, HC163, HC164, HC166,
                    HC175, HC191, HC245, HC273, HC377, HC540, HC688, SST39SF010, bus_pins,
                    pin_table)
from .kernel import KINDS, NEVER, Sim, Violation
