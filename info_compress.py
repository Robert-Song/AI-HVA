from kiutils.schematic import Schematic

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
            print(sch.labels[i])
            sch.labels[i].properties = newprop
        #sch.to_file("result.kicad_sch")
        return sch.to_sexpr()

    ''' Non-essential test case
    def bad_parse(self, filepath):
        sch = Schematic().from_file(filepath)
        newsch = Schematic()
        lb = sch.libSymbols
        newsch.libSymbols = lb
        newsch.to_file("result.kicad_sch")
    '''


#ic = InfoCompressor()
#print(ic.parse("example.kicad_sch"))