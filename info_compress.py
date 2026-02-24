from kiutils.schematic import Schematic
from kiutils.items.common import Effects
import subprocess
from kinparse import parse_netlist

class InfoCompressor:
    def __init__(self):
        pass

    def parse(self, filepath):
        sch = Schematic().from_file(filepath)
        sch.libSymbols = []
        for i in range(len(sch.schematicSymbols)):
            newprop = []
            sch.schematicSymbols[i].properties = newprop
        for i in range(len(sch.labels)):
            newprop = []
            #sch.labels[i].effects = Effects()
            #print(sch.labels[i])
        for i in range(len(sch.hierarchicalLabels)):
            newprop = []
            #print(sch.hierarchicalLabels[i])
            sch.hierarchicalLabels[i].properties = newprop
        #sch.to_file("result.kicad_sch")
        return sch.to_sexpr()
    
    def convert(self, filepath):
        sch = Schematic().from_file(filepath)
        newl = []
        banned = ["C", "R", "Fuse", "GND", "PWR_FLAG"]
        for sl in sch.libSymbols:
            allgood = True
            for bv in banned:
                if sl.entryName == bv:
                    allgood = False
                    break
            if allgood:
                newl.append(sl)
        sch.libSymbols = newl
        for i in range(len(sch.schematicSymbols)):
            newprop = []
            sch.schematicSymbols[i].properties = newprop
        for i in range(len(sch.labels)):
            newprop = []
            #sch.labels[i].effects = Effects()
            #print(sch.labels[i])
        for i in range(len(sch.hierarchicalLabels)):
            newprop = []
            #print(sch.hierarchicalLabels[i])
            sch.hierarchicalLabels[i].properties = newprop
        sch.to_file("result.kicad_sch")
        subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli", "sch", "export", "netlist", "result.kicad_sch"])
    
    def essential_list_netlist(self, filepath):
        for libb in parse_netlist(filepath).libparts:
            print(libb.name + ": " + libb.desc + f" ({libb.docs})")
    
    def essential_list_kicad(self, filepath):
        self.convert(filepath)
        self.essential_list_netlist("result.net")

#Test case
#ic = InfoCompressor()
#(ic.essential_list_kicad("example.kicad_sch"))