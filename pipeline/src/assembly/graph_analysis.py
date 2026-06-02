import logging
import networkx as nx
logger = logging.getLogger(__name__)

def compute_graph_analysis(stpa: dict) -> dict:
    G = nx.Graph()
    for comp_name, comp_data in stpa.get('components', {}).items():
        G.add_node(comp_name, **comp_data)
    for pair_id, pair_data in stpa.get('connection_pairs', {}).items():
        endpoints = pair_data.get('endpoints', [])
        path = pair_data.get('path') or endpoints
        if len(path) >= 2:
            for node in path:
                if node not in G:
                    G.add_node(node, component_id=node, component_class='passive', safety_critical=False)
            for a, b in zip(path, path[1:]):
                if G.has_edge(a, b):
                    G[a][b].setdefault('pair_ids', []).append(pair_id)
                else:
                    G.add_edge(a, b, pair_ids=[pair_id])
    if G.number_of_nodes() == 0:
        logger.warning('Empty graph — no components to analyze')
        return {'component_centrality': {}, 'connection_criticality': {}}
    degree_cent = nx.degree_centrality(G)
    betweenness_cent = nx.betweenness_centrality(G)
    if nx.is_connected(G):
        bridges = set(nx.bridges(G))
    else:
        bridges = set()
        for component_nodes in nx.connected_components(G):
            subgraph = G.subgraph(component_nodes)
            if subgraph.number_of_edges() > 0:
                bridges.update(nx.bridges(subgraph))
    component_centrality = {}
    for node in G.nodes():
        component_centrality[node] = {'degree': round(degree_cent[node], 4), 'betweenness': round(betweenness_cent[node], 4), 'is_hub': G.degree(node) > 5}
    connection_criticality = {}
    for pair_id, detail in stpa.get('connection_details', {}).items():
        endpoints = detail.get('endpoints', [])
        if len(endpoints) != 2:
            continue
        pair = stpa.get('connection_pairs', {}).get(pair_id, {})
        path = pair.get('path') or detail.get('path') or endpoints
        path_edges = list(zip(path, path[1:])) if len(path) >= 2 else [tuple(endpoints)]
        is_bridge = any((a, b) in bridges or (b, a) in bridges for a, b in path_edges)
        both_safety = all((stpa.get('components', {}).get(ep, {}).get('safety_critical', False) for ep in endpoints))
        ctrl_count = len(detail.get('control_actions', []))
        fb_count = len(detail.get('feedback_signals', []))
        if is_bridge and both_safety or (ctrl_count + fb_count > 3 and both_safety):
            priority = 'high'
        elif is_bridge or both_safety or ctrl_count + fb_count > 2:
            priority = 'medium'
        else:
            priority = 'low'
        connection_criticality[pair_id] = {'control_signal_count': ctrl_count, 'feedback_signal_count': fb_count, 'is_bridge': is_bridge, 'connects_safety_critical': both_safety, 'analysis_priority': priority, 'hop_count': pair.get('hop_count', detail.get('hop_count', 0)), 'path': path, 'intermediate_components': pair.get('intermediate_components', detail.get('intermediate_components', []))}
    logger.info(f"Graph analysis: {len(component_centrality)} components, {len(connection_criticality)} connections, {sum((1 for c in connection_criticality.values() if c['analysis_priority'] == 'high'))} high-priority")
    return {'component_centrality': component_centrality, 'connection_criticality': connection_criticality}
