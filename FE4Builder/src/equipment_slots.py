"""Stage new persistent slots with a unit's equipment, without early ROM writes."""
from copy import copy

from item_expansion import ItemExpansion


class EquipmentSlots:
    def __init__(self, rom):
        self.rom = rom
        self.assignments = {}
        self.snapshot = None
        self.preview = None

    def keep(self, slots):
        remaining = {slot: item for slot, item in self.assignments.items() if slot in slots}
        if remaining != self.assignments:
            self.assignments = remaining
            self.preview = None
        if not remaining:self.snapshot = None

    def view(self):
        if not self.assignments:return self.rom
        if bytes(self.rom.data) != self.snapshot:
            raise ValueError('The ROM changed in another editor. Reload this record before creating player slots.')
        if self.preview is None:
            trial = copy(self.rom);trial.data = bytearray(self.rom.data)
            for slot, item in sorted(self.assignments.items()):ItemExpansion(trial).add_slot(item, slot=slot)
            self.preview = trial
        return self.preview

    def stage(self, item, slot):
        if type(item) is not int or type(slot) is not int:raise ValueError('Choose numeric item and player slot IDs.')
        source = self.view()
        trial = copy(source);trial.data = bytearray(source.data)
        ItemExpansion(trial).add_slot(item, slot=slot)
        if not self.assignments:self.snapshot = bytes(self.rom.data)
        self.assignments[slot] = item
        self.preview = trial
