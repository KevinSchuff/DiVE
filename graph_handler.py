import networkx as nx
from CSVHandler import bg_url_from_csv_value
from urllib.parse import urlencode

def remove_duplicate_dies(dies):
    seen = {}
    for die in dies:
        key = (str(die.get("id")), die.get("typ"))
        seen[key] = {"id": key[0], "typ": key[1]}
    return list(seen.values())

def add_edges_by_mode(G: nx.Graph, front_key: str, back_key: str, mode: str = 'both'):
    """
    Add edges in coinview based on matching dies and depending on selected edge mode.

    """
    # Each item is (node id, node attributes dict)
    nodes = list(G.nodes(data=True))
    # compare every node pair 
    for i in range(len(nodes) - 1):
        u_id, u_dict = nodes[i]    
        # extract relevant attributes from node u
        front_u = str(u_dict.get(front_key, "")).strip()
        back_u = str(u_dict.get(back_key, "")).strip()

        for j in range(i + 1, len(nodes)):
            v_id, v_dict = nodes[j]
            # extract relevant attributes from node v
            front_v = str(v_dict.get(front_key, "")).strip()
            back_v = str(v_dict.get(back_key, "")).strip()

            if mode == 'front' and front_u and front_u == front_v:
                G.add_edge(u_id, v_id, attr='same_front', label=front_u)
            elif mode == 'back' and back_u and back_u == back_v:
                G.add_edge(u_id, v_id, attr='same_back', label=back_u)
            elif mode == 'both' and front_u and back_u and front_u == front_v and back_u == back_v:
                G.add_edge(u_id, v_id, attr='same_front_back', label=(front_u + '/' + back_v))

def create_dies_graph(coin_graph, front_col, back_col, hidden_coins=None, hidden_dies=None, front_url_col=None, back_url_col=None):
    """
    Build die-graph skipping over hidden coins and dies.
    """
    die_graph = nx.Graph()
    skip_coins = set(hidden_coins or [])
    skip_dies = set(hidden_dies)
    max_edge_weight = 0
    # go through all nodes in coin_graph
    for node_id, data in coin_graph.nodes(data=True):
        # ignore hidden coins
        if node_id in skip_coins:
            continue
        coin_id = str(node_id)
        front_die = data.get(front_col)
        back_die = data.get(back_col)
        # add coin's back die, to die graph
        skip_front_die = (not front_die) or (front_die in skip_dies) 
        skip_back_die = (not back_die) or (back_die in skip_dies) 

        if not skip_front_die:
            if front_die not in skip_dies:
                if front_die not in die_graph:
                    die_graph.add_node(front_die, typ=front_col, coin_ids=set())
                die_graph.nodes[front_die]["coin_ids"].add(coin_id)
                # assign image once if available
                if front_url_col and data.get(front_url_col) and "bg_die" not in die_graph.nodes[front_die]:
                    bg = bg_url_from_csv_value(data.get(front_url_col))
                    if bg:
                        die_graph.nodes[front_die]["bg_die"] = bg
        # add coin's back die to die graph
        if not skip_back_die:
            if back_die not in die_graph:
                die_graph.add_node(back_die, typ=back_col, coin_ids=set())
            die_graph.nodes[back_die]["coin_ids"].add(coin_id)
            # assign image once if available
            if back_url_col and data.get(back_url_col) and "bg_die" not in die_graph.nodes[back_die]:
                bg = bg_url_from_csv_value(data.get(back_url_col))
                if bg:
                    die_graph.nodes[back_die]["bg_die"] = bg

        # connect front <-> back with weight
        if not skip_front_die and not skip_back_die:
            if die_graph.has_edge(front_die, back_die):
                die_graph[front_die][back_die]['weight'] += 1
            else:
                die_graph.add_edge(front_die, back_die, weight=1)
            # update max edge weight
            if die_graph[front_die][back_die]['weight'] > max_edge_weight:
                max_edge_weight = die_graph[front_die][back_die]['weight']

    for n in die_graph.nodes:
        ids = sorted(str(x) for x in die_graph.nodes[n]["coin_ids"])
        die_graph.nodes[n]["coin_ids"] = ids
        die_graph.nodes[n]["coin_ids_string"] = "," + ",".join(sorted(ids)) + ","

    return die_graph, max_edge_weight


def nx_to_elements(G: nx.Graph):
    """
    Convert NetworkX graph into dash cytoscape elements list
    """
    elements = []
    # add all nodes with attributes to elements
    for node_id, node_attributes in G.nodes(data=True):
        node_data = {"id": str(node_id), "label": str(node_id),}
        # add all other node attributes
        for attribute_name, attribute_value in node_attributes.items():
            node_data[str(attribute_name)] = attribute_value
        elements.append({"data": node_data})
    # add all edges with attributes to elements
    for u, v, edge_attributes in G.edges(data=True):
        edge_data = {'source': str(u), 'target': str(v)}
        # add all other edge attributes
        for attribute_name, attribute_value in edge_attributes.items():
            edge_data[str(attribute_name)] = attribute_value
        elements.append({"data": edge_data})

    return elements

def cyto_elements_to_nx(elements, exclude_hidden):
    """
    converts cyto elements list to networkX graph
    """

    graph = nx.Graph()
    # collect hidden nodes
    hidden_nodes = set()
    if exclude_hidden:
        for ele in elements:
            # check that element is node
            if "data" in ele and "id" in ele["data"]:
                # check for hidden node specific styling
                if ele.get("style", {}).get("display") == "none":
                    hidden_nodes.add(str(ele["data"]["id"]))

    # add visible nodes and skip hidden nodes
    for ele in elements:
        data = ele.get("data", {})
        # check that element is node
        if "id" in data:
            node_id = str(data["id"])
            if node_id not in hidden_nodes:
                graph.add_node(node_id)
    
    # add edges
    for ele in elements:
        data = ele.get("data", {})
        if "source" in data and "target" in data:
            u = str(data["source"])
            v = str(data["target"])
            # skip if one node of edge is hidden
            if u in hidden_nodes or v in hidden_nodes:
                continue
            graph.add_edge(u, v)

    return graph

def enrich_images(G, base_elements, front_img_col_norm, back_img_col_norm):
    """
    adds images URLs to Cytoscape nodes
    """

    # build dict: node_id ->(front_url, back_url)
    url_by_id = {}
    for n_id, n_dict in G.nodes(data=True):
        front_url = bg_url_from_csv_value(n_dict.get(front_img_col_norm))
        back_url = bg_url_from_csv_value(n_dict.get(back_img_col_norm))
        url_by_id[str(n_id)] = (front_url, back_url)

    # Enrich base elements with bg_* fields
    enriched = []
    for ele in base_elements:
        if not isinstance(ele, dict) or 'data' not in ele or 'id' not in ele['data']:
            enriched.append(ele)
            continue

        ele_id = str(ele['data']['id'])
        front_url, back_url = url_by_id.get(ele_id, (None, None))

        new_data = dict(ele['data'])
        if front_url:
            new_data['bg_front'] = front_url
        if back_url:
            new_data['bg_back'] = back_url
        if front_url and back_url:
            # Optional merged preview for edge-mode == 'both'
            params = {'w': 200, 'h': 200, 'front': front_url, 'back': back_url}
            new_data['bg_split'] = f"/merge_split?{urlencode(params)}"

        enriched.append({'data': new_data})

    return enriched