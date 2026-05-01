import json
from src.ingestion.netlist_loader import load_netlist

netlist = load_netlist('netlist/rffe.net')
components = netlist.get('components', {})

cids = ['C806', 'C818', 'L802', 'L809', 'L810', 'L811', 'R805', 'U802', 'U804', 'U816']
for cid in cids:
    comp = components.get(cid, {})
    print(f"{cid}: {comp.get('datasheet_url')}")
