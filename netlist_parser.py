import sys
import re
import json
import datetime
import math
from collections import defaultdict

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

def parse_s_expr(s):
    # Simple S-expression parser.
    # Converts (key value) into nested lists: ['key', 'value'].
    s = s.replace('(', ' ( ').replace(')', ' ) ')
    tokens = s.split()
    stack = [[]]
    
    for token in tokens:
        if token == '(':
            sub_list = []
            stack[-1].append(sub_list)
            stack.append(sub_list)
        elif token == ')':
            if len(stack) > 1:
                stack.pop()
        else:
            # Handle quoted strings specifically
            if token.startswith('"') and token.endswith('"'):
                stack[-1].append(token[1:-1])
            else:
                stack[-1].append(token)
    return stack[0][0]

def extract_netlist_data(file_content):
    # Main extraction logic for KiCad .net files.
    # pre-process to handle S-expression parsing quoted strings / spaces stuffs
    content = re.sub(r'"([^"]*)"', lambda m: '"' + m.group(1).replace(' ', '_SPACE_') + '"', file_content)
    parsed = parse_s_expr(content)
    
    # data containers
    data = {"metadata": {}, "components": {}, "nets": {}}

    # recursive search for specific blocks
    def find_block(tree, keyword):
        if isinstance(tree, list) and len(tree) > 0:
            if tree[0] == keyword:
                return tree
            for item in tree:
                res = find_block(item, keyword)
                if res: return res
        return None

    # metadata
    design_block = find_block(parsed, 'design')
    if design_block:
        source_node = find_block(design_block, 'source')
        date_node = find_block(design_block, 'date')
        if source_node: data["metadata"]["source"] = source_node[1].replace('_SPACE_', ' ')
        if date_node: data["metadata"]["date"] = date_node[1]

    # components
    # structure: (components (comp (ref "X") ...))
    components_block = find_block(parsed, 'components')
    if components_block:
        for item in components_block:
            if isinstance(item, list) and item[0] == 'comp':
                ref_node = find_block(item, 'ref')
                val_node = find_block(item, 'value')
                lib_node = find_block(item, 'libsource')
                
                ref = ref_node[1] if ref_node else "UNKNOWN"
                value = val_node[1] if val_node else ""
                desc = ""
                
                # extract description from libsource if available
                if lib_node:
                     desc_idx = lib_node.index('description') if 'description' in lib_node else -1
                     if desc_idx != -1:
                         desc = lib_node[desc_idx + 1].replace('_SPACE_', ' ')

                data["components"][ref] = {
                    "id": ref,
                    "value": value,
                    "raw_desc": desc
                }

    # nets
    # structure: (nets (net (code "1") (name "X") (node (ref "Y")...) ...))
    nets_block = find_block(parsed, 'nets')
    if nets_block:
        for item in nets_block:
            if isinstance(item, list) and item[0] == 'net':
                name_node = find_block(item, 'name')
                net_name = name_node[1].replace('_SPACE_', ' ') if name_node else "UNKNOWN"
                
                # find all nodes (connections) in this net
                nodes = []
                for sub in item:
                    if isinstance(sub, list) and sub[0] == 'node':
                        ref_node = find_block(sub, 'ref')
                        pin_node = find_block(sub, 'pin')
                        pintype_node = find_block(sub, 'pintype')
                        pinfunction_node = find_block(sub, 'pinfunction')
                        if ref_node:
                            nodes.append({
                                'ref': ref_node[1],
                                'pin': pin_node[1] if pin_node else '',
                                'pintype': pintype_node[1] if pintype_node else 'unknown',
                                'pinfunction': pinfunction_node[1] if pinfunction_node else ''
                            })
                
                data["nets"][net_name] = nodes

    return data

def build_stpa_json(raw_data):
    # transforms raw netlist data into the specific STPA JSON template.
    output = {
        "system_metadata": {},
        "connection_pairs": {},
        "components": {},
        "connection_details": {},
        "graph_analysis": {
            "component_centrality": {},
            "connection_criticality": {}
        }
    }

    # metadata
    source_path = raw_data["metadata"].get("source", "unknown.sch")
    system_name = source_path.replace("\\", "/").split("/")[-1].replace(".kicad_sch", "")
    
    output["system_metadata"] = {
        "system_name": system_name,
        "netlist_source": source_path,
        "analysis_date": datetime.datetime.now().isoformat()
    }

    # graph connectivity analysis
    # adjacency list: component -> set of connected components
    adjacency = defaultdict(set)
    # pair info: tuple(sorted(comp1, comp2)) -> {nets: set(), signals: ...}
    pair_info = defaultdict(lambda: {"nets": set(), "signals": defaultdict(list)})

    for net_name, nodes in raw_data["nets"].items():
        comps_on_net = defaultdict(list)
        for node in nodes:
            comps_on_net[node["ref"]].append(node)
        
        # unique components on this net
        unique_refs = sorted(list(comps_on_net.keys()))
        
        for i in range(len(unique_refs)):
            u = unique_refs[i]
            if u not in raw_data["components"]: continue # skip if comp not found (e.g. metadata)
            
            for j in range(i + 1, len(unique_refs)):
                v = unique_refs[j]
                if v not in raw_data["components"]: continue

                # register connection for graph analysis
                adjacency[u].add(v)
                adjacency[v].add(u)

                # register connection for connection pairs
                pair_key = tuple(sorted((u, v)))
                pair_info[pair_key]["nets"].add(net_name)

                # Determine direction if possible by comparing pin types
                u_types = {n['pintype'] for n in comps_on_net[u]}
                v_types = {n['pintype'] for n in comps_on_net[v]}
                
                from_ref = "<DET/LLM>"
                to_ref = "<DET/LLM>"
                
                # Basic inference of signal direction if strictly output -> input exists
                if 'output' in u_types and 'input' in v_types and 'output' not in v_types:
                    from_ref = u
                    to_ref = v
                elif 'output' in v_types and 'input' in u_types and 'output' not in u_types:
                    from_ref = v
                    to_ref = u

                sig = {
                    "from": from_ref,
                    "to": to_ref,
                    "signal_name": net_name
                }
                
                # Prevent duplicates
                if sig not in pair_info[pair_key]["signals"][net_name]:
                    pair_info[pair_key]["signals"][net_name].append(sig)

    # Compute graph metrics using networkx if available
    if HAS_NX:
        G = nx.Graph()
        for ref in raw_data["components"]:
            G.add_node(ref)
        for u in adjacency:
            for v in adjacency[u]:
                G.add_edge(u, v)
        betweenness_dict = nx.betweenness_centrality(G, normalized=True)
        bridge_edges = list(nx.bridges(G)) if hasattr(nx, 'bridges') else []
    else:
        betweenness_dict = {}
        bridge_edges = []

    # populate components
    for ref, details in raw_data["components"].items():
        # calculate connections
        connected_list = sorted(list(adjacency[ref]))
        
        output["components"][ref] = {
            "component_id": ref,
            "component_class": "<LLM: controller | actuator | sensor | ...>",
            "functional_description": f"<LLM: Context: {details['raw_desc']}>",
            "safety_critical": "<LLM: boolean>",
            "connected_to": connected_list
        }
        
        # calculate centrality (degree centrality)
        # degree = connections / (total_components - 1)
        total_comps = len(raw_data["components"])
        degree = len(connected_list) / (total_comps - 1) if total_comps > 1 else 0
        
        betweenness_val = round(betweenness_dict.get(ref, 0), 4) if HAS_NX else "<DET: Requires NetworkX>"
        
        output["graph_analysis"]["component_centrality"][ref] = {
            "degree": round(degree, 4),
            "betweenness": betweenness_val,
            "is_hub": len(connected_list) > 4 # HACK: arbitrary threshold from template
        }

    # populate connection pairs & details
    for pair, info in pair_info.items():
        u, v = pair
        conn_id = f"{u}-{v}"
        net_list = sorted(list(info["nets"]))
        
        # connection pairs
        output["connection_pairs"][conn_id] = {
            "endpoints": [u, v],
            "net_count": len(net_list),
            "net_names": net_list
        }
        
        # connection details 
        control_actions = []
        for net_name in net_list:
            sigs = info["signals"].get(net_name, [])
            if not sigs:
                sigs = [{"from": "<DET/LLM>", "to": "<DET/LLM>", "signal_name": net_name}]
            for sig in sigs:
                control_actions.append({
                    "from": sig["from"],
                    "to": sig["to"],
                    "signal_name": sig["signal_name"],
                    "action_type": "<LLM>",
                    "purpose": "<LLM>",
                    "timing_constraint": "<LLM>"
                })
        
        output["connection_details"][conn_id] = {
            "endpoints": [u, v],
            "physical_interface": "<LLM: I2C, SPI, GPIO...>",
            "control_actions": control_actions,
            "feedback_signals": [],
            "source": ["schematic_netlist"],
            "notes": "<LLM>"
        }

        # connection criticality (graph analysis)
        is_bridge_val = "<DET: Requires Graph Algo>"
        if HAS_NX:
            is_bridge_val = (u, v) in bridge_edges or (v, u) in bridge_edges

        output["graph_analysis"]["connection_criticality"][conn_id] = {
            "control_signal_count": "<LLM>",
            "feedback_signal_count": "<LLM>",
            "is_bridge": is_bridge_val,
            "connects_safety_critical": "<LLM>",
            "analysis_priority": "<LLM>"
        }

    return output

if __name__ == "__main__":
    import os
    
    netlist_file = "input/example.net"
    output_file = "output/temp_output.json"

    # Allow overriding via command line
    if len(sys.argv) > 1:
        netlist_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    try:
        with open(netlist_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        raw_extracted = extract_netlist_data(content)
        stpa_output = build_stpa_json(raw_extracted)
        
        # Create output directory if it doesn't exist
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stpa_output, f, indent=2)
            
        print(f"Successfully processed '{netlist_file}' and wrote output to '{output_file}'")
    except FileNotFoundError:
        print(f"Error: File '{netlist_file}' not found. Please ensure the path exists.")
        sys.exit(1)