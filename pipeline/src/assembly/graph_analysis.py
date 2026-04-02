import logging
import networkx as nx
logger = logging.getLogger(__name__)

def compute_graph_analysis(stpa: dict) -> dict:
    G = nx.Graph()
    for comp_name, comp_data in stpa.get('components', {}).items():
        G.add_node(comp_name, **comp_data)
    for pair_id, pair_data in stpa.get('connection_pairs', {}).items():
        endpoints = pair_data.get('endpoints', [])
        if len(endpoints) == 2:
            G.add_edge(endpoints[0], endpoints[1], pair_id=pair_id)
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
        edge = tuple(endpoints)
        reverse_edge = (endpoints[1], endpoints[0])
        is_bridge = edge in bridges or reverse_edge in bridges
        both_safety = all((stpa.get('components', {}).get(ep, {}).get('safety_critical', False) for ep in endpoints))
        ctrl_count = len(detail.get('control_actions', []))
        fb_count = len(detail.get('feedback_signals', []))
        if is_bridge and both_safety or (ctrl_count + fb_count > 3 and both_safety):
            priority = 'high'
        elif is_bridge or both_safety or ctrl_count + fb_count > 2:
            priority = 'medium'
        else:
            priority = 'low'
        connection_criticality[pair_id] = {'control_signal_count': ctrl_count, 'feedback_signal_count': fb_count, 'is_bridge': is_bridge, 'connects_safety_critical': both_safety, 'analysis_priority': priority}
    logger.info(f"Graph analysis: {len(component_centrality)} components, {len(connection_criticality)} connections, {sum((1 for c in connection_criticality.values() if c['analysis_priority'] == 'high'))} high-priority")
    return {'component_centrality': component_centrality, 'connection_criticality': connection_criticality}