from kiutils.schematic import Schematic
from kiutils.items.common import Effects
import subprocess
from kinparse import parse_netlist
import os
from cli import get_kicad_cli_path

class InfoCompressor:
    def __init__(self):
        self.seen_files = {}


    def check_duplicate_file(self, filename, filecontent):
        valid = False
        replacement = filecontent
        if not filename in self.seen_files.keys():
            valid = True
        elif len(filecontent) != len(self.seen_files[filename]):
            valid = True
        elif filecontent != self.seen_files[filename]:
            valid = True
        if valid:
             self.seen_files[filename] = filecontent
        else:
             print(f"Warning: {filename} is a duplicate file, discard")
        del filecontent
        replacement = self.seen_files[filename]
        return valid, replacement


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
   
    def convert(self, filepath, output):
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
        #sch.libSymbols = newl
        for i in range(len(sch.schematicSymbols)):
            newprop = []
            #sch.schematicSymbols[i].properties = newprop
        for i in range(len(sch.labels)):
            newprop = []
            #sch.labels[i].effects = Effects()
            #print(sch.labels[i])
        for i in range(len(sch.hierarchicalLabels)):
            newprop = []
            #print(sch.hierarchicalLabels[i])
            #sch.hierarchicalLabels[i].properties = newprop
        sch.to_file(output)
        #print(get_kicad_cli_path())
        #print(get_kicad_cli_path(), "sch", "export", "netlist", output)
        subprocess.run([get_kicad_cli_path(), "sch", "export", "netlist", output])


    def convert_whitelist_kicad(self, filepath, whitelist, output):
        sch = Schematic().from_file(filepath)
        newl = []
        for sl in sch.libSymbols:
            #print(sl)
            if sl.entryName in whitelist:
                newl.append(sl)
        sch.libSymbols = newl
        for i in range(len(sch.schematicSymbols)):
            newprop = []
            #sch.schematicSymbols[i].properties = newprop
        for i in range(len(sch.labels)):
            newprop = []
            # sch.labels[i].effects = Effects()
            # print(sch.labels[i])
        for i in range(len(sch.hierarchicalLabels)):
            newprop = []
            # print(sch.hierarchicalLabels[i])
            #sch.hierarchicalLabels[i].properties = newprop
        sch.to_file(output)
        #print(get_kicad_cli_path(), "sch", "export", "netlist", output)
        subprocess.run([get_kicad_cli_path(), "sch", "export", "netlist", output])
    def convert_whitelist_netlist(self, filepath, whitelist, output):
        sch = Schematic().from_file(filepath)
        newl = []
        for sl in sch.libSymbols:
            if sl.entryName in whitelist:
                newl.append(sl)
        #sch.libSymbols = newl
        for i in range(len(sch.schematicSymbols)):
            newprop = []
            #sch.schematicSymbols[i].properties = newprop
        for i in range(len(sch.labels)):
            newprop = []
            # sch.labels[i].effects = Effects()
            # print(sch.labels[i])
        for i in range(len(sch.hierarchicalLabels)):
            newprop = []
            # print(sch.hierarchicalLabels[i])
            #sch.hierarchicalLabels[i].properties = newprop
        sch.to_file(output)
        #print(get_kicad_cli_path(), "sch", "export", "netlist", output)
        subprocess.call([get_kicad_cli_path(), "sch", "export", "netlist", output])


    def essential_list_netlist(self, filepath, mode='L'):
        col = []
        banned = ["C", "R", "Fuse", "GND", "PWR_FLAG", "Signature"]
        for libb in parse_netlist(filepath).libparts:
            desc = libb.desc if libb.desc else "?"
            footprint = next((f[1] for f in libb.fields if len(f) > 1 and f[0] == "Footprint"), "")
            entry = (libb.name, desc, libb.docs, libb.lib, libb.pins, footprint)
            if mode == 'L':
                col.append(entry)
            elif mode == 'M':
                if "logo" not in libb.name.lower():
                    col.append(entry)
            elif mode == 'H':
                if "logo" not in libb.name.lower() and libb.name not in banned and "~" not in libb.docs:
                    col.append(entry)
        return col
   
    def essential_list_kicad(self, filepath, mode='L'):
        self.convert(filepath, "result.kicad_sch")
        return self.essential_list_netlist("result.net", mode)


#Test case for US#5
#os.chdir("./test/info_compress")

#ic = InfoCompressor()
#ic.convert_whitelist_kicad("sidloc.kicad_sch", [], "test.kicad_sch")


#Test case for US#20
'''
os.chdir("./test/info_compress")
#os.chdir("./test/info_compress")
ic = InfoCompressor()
adata = "ahahahah"
bdata = "hehehehe"
_, adata = ic.check_duplicate_file("test.txt", adata)
_, adata = ic.check_duplicate_file("test2.txt", adata)
_, adata = ic.check_duplicate_file("test.txt", bdata)
_, bdata = ic.check_duplicate_file("test.txt", adata)
'''