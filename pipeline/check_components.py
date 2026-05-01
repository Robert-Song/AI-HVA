import json
from src.ingestion.netlist_loader import load_netlist

netlist = load_netlist('netlist/rffe.net')
components = netlist.get('components', {})

print("ID\tPart Number\tValue\tFootprint")
print("-" * 60)
for cid, comp in components.items():
    print(f"{cid}\t{comp.get('part_number', 'N/A')}\t{comp.get('value', 'N/A')}\t{comp.get('footprint', 'N/A')}")
