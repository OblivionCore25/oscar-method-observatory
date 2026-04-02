import networkx as nx

def compute_graph_metrics(graph: nx.DiGraph) -> dict[str, dict]:
    """
    Compute betweenness centrality, PageRank, community assignments, and blast radius.
    Returns a dict: node_id → {betweenness, pagerank, community_id, blast_radius}
    """
    if len(graph) == 0:
        return {}

    # 1. Centrality and PageRank
    betweenness = nx.betweenness_centrality(graph, normalized=True)
    
    # PageRank occasionally fails to converge quickly on disconnected graphs,
    # but networkx defaults to max_iter=100 which typically handles standard AST graphs safely.
    try:
        pagerank = nx.pagerank(graph, alpha=0.85)
    except Exception:
        pagerank = {node: 0.0 for node in graph.nodes}

    # 2. Community Detection (Louvain)
    # Exclude external 'unresolved' nodes to not skew internal module communities
    internal_subgraph = graph.subgraph([n for n in graph.nodes if not n.startswith("unresolved:")])
    undirected = internal_subgraph.to_undirected()
    
    community_map = {}
    try:
        # Require networkx >= 2.7
        communities = nx.community.louvain_communities(undirected, seed=42)
        for community_id, community_set in enumerate(communities):
            for node_id in community_set:
                community_map[node_id] = community_id
    except AttributeError:
        # Graceful fallback if networkx version is too old
        pass

    # 3. Blast Radius (Transitive closure reachable nodes)
    blast_radius = {}
    for node in internal_subgraph.nodes:
        reachable = nx.descendants(internal_subgraph, node)
        blast_radius[node] = len(reachable)

    return {
        node: {
            "betweenness_centrality": round(betweenness.get(node, 0.0), 6),
            "pagerank": round(pagerank.get(node, 0.0), 6),
            "community_id": community_map.get(node),
            "blast_radius": blast_radius.get(node, 0),
        }
        for node in graph.nodes
    }
