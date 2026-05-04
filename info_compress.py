from kiutils.schematic import Schematic
from kiutils.items.common import Effects
import subprocess
from kinparse import parse_netlist
import os
from cli import get_kicad_cli_path

class InfoCompressor:
    def __init__(self):
        self.seen_files = {}


    def read_schematic(self, filepath):
        return Schematic().from_file(filepath, encoding="utf-8")


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
        sch = self.read_schematic(filepath)
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
        sch = self.read_schematic(filepath)
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
        sch.to_file(output, encoding="utf-8")
        #print(get_kicad_cli_path())
        #print(get_kicad_cli_path(), "sch", "export", "netlist", output)
        subprocess.run([get_kicad_cli_path(), "sch", "export", "netlist", output])


    def convert_whitelist_kicad(self, filepath, whitelist, output):
        sch = self.read_schematic(filepath)
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
        sch.to_file(output, encoding="utf-8")
        #print(get_kicad_cli_path(), "sch", "export", "netlist", output)
        subprocess.run([get_kicad_cli_path(), "sch", "export", "netlist", output])
    def convert_whitelist_netlist(self, filepath, whitelist, output):
        sch = self.read_schematic(filepath)
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
        sch.to_file(output, encoding="utf-8")
        #print(get_kicad_cli_path(), "sch", "export", "netlist", output)
        subprocess.call([get_kicad_cli_path(), "sch", "export", "netlist", output])


    def essential_list_netlist(self, filepath):
        col = []
        banned = ["C", "R", "Fuse", "GND", "PWR_FLAG", "Signature"]
        for libb in parse_netlist(filepath).libparts:
            print(libb)
            print(libb.name + ": " + libb.desc + f" ({libb.docs})")
            desc = "?"
            if libb.desc:
                desc = libb.desc
            if ("logo" not in libb.name.lower()) and (True or (libb.name not in banned and "~" not in libb.docs)):

                col.append((libb.name, desc, libb.docs))
        return col
   
    def essential_list_kicad(self, filepath):
        self.convert(filepath, "result.kicad_sch")
        return self.essential_list_netlist("result.net")


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
