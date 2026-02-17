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

        sch.to_file("result.kicad_sch")
        print(len(sch.schematicSymbols))


ic = InfoCompressor()
ic.parse("example.kicad_sch")
