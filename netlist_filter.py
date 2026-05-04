import sexpdata
import re

def get_prefix(ref):
    match = re.match(r"[A-Za-z]+", ref)
    return match.group(0) if match else ""

def parse_netlist(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return sexpdata.loads(f.read())
        
def find_section(tree, name):
    for item in tree:
        if isinstance(item, list) and item[0].value() == name:
            return item
    return None

def filter_components(components, whitelist):
    kept_comps = set()
    new_comps = [components[0]]  # keep 'components' symbol

    for comp in components[1:]:
        compname = None
        ref = None
        for field in comp:
            #print(field)
            if isinstance(field, list) and field[0].value() == "value":
                compname = field[1]
            if isinstance(field, list) and field[0].value() == "ref":
                ref = field[1]

        if compname:
            if compname in whitelist:
                new_comps.append(comp)
                kept_comps.add(compname)

    return new_comps, kept_comps

def filter_nets(nets, kept_comps):
    new_nets = [nets[0]]

    for net in nets[1:]:
        new_nodes = []

        for item in net:
            if isinstance(item, list) and item[0].value() == "node":
                compname = None
                for field in item:
                    if isinstance(field, list) and field[0].value() == "value":
                        compname = field[1]
                        break

                if compname in kept_comps:
                    new_nodes.append(item)

        if len(new_nodes) >= 2:
            new_net = [net[0]] 
            for item in net[1:]:
                if not (isinstance(item, list) and item[0].value() == "node"):
                    new_net.append(item)

            new_net.extend(new_nodes)
            new_nets.append(new_net)

    return new_nets

def rebuild_tree(tree, new_components, new_nets):
    new_tree = []

    for item in tree:
        if isinstance(item, list):
            key = item[0].value()

            if key == "components":
                new_tree.append(new_components)
            elif key == "nets":
                new_tree.append(new_nets)
            else:
                new_tree.append(item)
        else:
            new_tree.append(item)

    return new_tree

def write_netlist(tree, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(sexpdata.dumps(tree))

def filter_netlist_full(oldnetlist, whitelist, output):
    tree = parse_netlist(oldnetlist)
    components = find_section(tree, "components")
    nets = find_section(tree, "nets")
    new_components, kept_refs = filter_components(components, whitelist)
    new_nets = filter_nets(nets, kept_refs)
    new_tree = rebuild_tree(tree, new_components, new_nets)
    write_netlist(new_tree, output)

if __name__ == "__main__":
    filter_netlist_full("result.net", ["SolderJumper_2_Open"], "filtered2.net")
