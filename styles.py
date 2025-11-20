"""
Helpers for bulding dash cytoscape stylesheets.
"""

# stylesheet generation
_css_esc = str.maketrans({"\\": r"\\\\", '"': r"\\\"", "'": r"\\'", "]": r"\\]", "[": r"\\["})
# make string safe to embed inside cytoscape attribute selector
def css_escape(s):
    """
    Escape a string for safe use inside cytoscape attribute selectors.

    Parameters
    ----------
    s : str
        String to escape.

    Returns
    -------
    str
        Escaped string, safe to embed in cytoscape selectors.
    """

    return str(s).translate(_css_esc)

def base_stylesheet_dies(scale_edges_weight=False, max_edge_weight = 0):
    """
    Build the cytoscape base stylesheet for the die-view.
    Nodes display their label and optionally a background image for dies.
    Edges display their weight and edge width can be scaled based on edge weight.
    Selected Nodes are highlighted with thicker border.

    Parameters
    ----------
    scale_edges_weight : bool
        If true, edges will be scaled with their weight.
    max_edge_weight : int
        Maximum edge weight in the die-graph.

    Returns
    -------
    list of dict
        List of cytoscape stylesheet rule dictionaries for the die-view.
    """

    stylesheet = [
        {'selector': 'node', 'style': {'label': 'data(label)'}},
        {
            'selector': 'edge',
            'style': {
                'label': 'data(weight)',
                'font-size': 12,
                'min-zoomed-font-size': 8,
                'text-rotation': 'autorotate',
                'line-color': 'black',
                'text-margin-y': -15,
                'width': 2,
                'border-color': 'black'
            }
        },
        {
            'selector': 'node[bg_die]', # nur wenn es eine bg_die gibt
            'style': {
                'background-image': 'data(bg_die)',
                'background-fit': 'cover',
                'background-opacity': 1,
                'width': 200,
                'height': 200,
                'border-width': 4,
                'text-background-color': '#ffffff',
                'text-background-opacity': 0.5,
                'text-background-shape': 'round-rectangle'
            }
        },
        {'selector': ':selected', 'style': {'border-width': 8, "background-color": "#999"}},     # change styling of node selection
    ]

    if scale_edges_weight:
        stylesheet.append({
            'selector': 'edge',
            'style': {
                'width': f'mapData(weight, 0, {max_edge_weight}, 1, 20)'
            }
        })

    return stylesheet


def base_stylesheet_coins(edge_mode='front'):
    """
    Build the cytoscape base stylesheet for the coin-view.
    Nodes display their label and based on edge_mode a background image.
    Edges display display the corresponding dies as label, which are used to connect the nodes(coins).
    Selected Nodes are highlighted with thicker border.

    Parameters
    ----------
    edge_mode : str
        String contains currenty selected edge mode for coin-view. Is either front, back or both.

    Returns
    -------
    list of dict
        List of cytoscape stylesheet rule dictionaries for the coin-view.
    """

    styles = [
        {'selector': 'node', 'style': {'label': 'data(label)', 'width': 200, 'height': 200,'border-width': 4, 'border-color': 'black'}},
        {
            'selector': 'edge',
            'style': {
                'label': 'data(label)',
                'font-size': 12,
                'min-zoomed-font-size': 8,
                'text-rotation': 'autorotate',
                'line-color': 'black',
                'text-margin-y': -10,
                'width': 2,
            }
        },
        {'selector': ':selected', 'style': {'border-width': 8, "background-color": "#999"}},     # change styling of node selection
    ]

    # Common visual for image nodes
    def _img_rule(key: str):
        return {
            'selector': f'node[{key}]',
            'style': {
                'background-image': f'data({key})',
                'background-fit': 'contain',   # keep full coin visible
                'background-clip': 'node',
                'background-opacity': 1,
            }
        }

    if edge_mode == 'front':
        styles.append(_img_rule('bg_front'))

    elif edge_mode == 'back':
        styles.append(_img_rule('bg_back'))
    else:
        # mode == 'both': lowest → highest priority (later wins)
        styles.append(_img_rule('bg_back'))   # fallback 2
        styles.append(_img_rule('bg_front'))  # fallback 1
        styles.append(_img_rule('bg_split'))  # preferred

    return styles


def set_hiding_rules(filter_store, skip_coins, skip_dies):
    """
    Helper to build cytoscape stylesheet rules for hiding specific nodes

    Parameters
    ----------
    filter_store : dict or None
        Contains mapping from attribute name to list of values.
    skip_coins : list of str or None
        List of strings, where every str is the coin_id of a coin. These are supposed to be skipped while creating the die-graph.
    skip_dies : list of dict or None
        List of die dictionaries, where every die dictionary represents a die with keys id and typ.
        These are supposed to be skipped while creating the die-graph.

    Returns
    -------
    list of dict
        A list of Cytoscape stylesheet rule dictionaries that set display: none for matching nodes.
    """

    hiding_rules = []

    # hide nodes based on selection
    for node_id in skip_coins:
        hiding_rules.append({'selector': f"node[id='{css_escape(node_id)}']", 'style': {'display': 'none'}})
    for die in skip_dies:
        die_id = die.get("id")
        die_typ = die.get("typ")
        hiding_rules.append({'selector': f"node[{css_escape(die_typ)}='{css_escape(die_id)}']", 'style': {'display': 'none'}})

    # hide nodes based on attributes
    if isinstance(filter_store, dict):
        for attr, values in filter_store.items():
            for val in values or []:
                hiding_rules.append({
                    'selector': f"node[{attr}='{css_escape(val)}']",
                    'style': {'display': 'none'}
                })

    return hiding_rules


def set_color_rules(color_values_list, color_ids):
    """
    Helper to build cytoscape stylesheet rules for coloring specific nodes

    Each entry in ``color_values_list`` describes a set of attribute
    conditions, and the corresponding entry in ``color_ids`` provides
    the color to use. For each pair, a selector is constructed and a
    border color is applied.

    Parameters
    ----------
    color_values_list : list of list of str
        Each element in the list is a list of condition strings (looking like attr=value) for a particular color.
        Nodes with the logical conjuction of attribute values should be colored.
    color_ids : list of dict
        List of dash component id's like where the index field contains the color name or hex code, which should be applied.

    Returns
    -------
    list of dict
        A list of Cytoscape stylesheet rule dictionaries that set bordercolor for matching nodes.
    """

    color_rules = []
    # iterate over both lists in parallel, each pair represents one dropdown
    for color_values, id_ in zip(color_values_list or [], color_ids or []):
        # extract index field, which stores the color
        color = id_.get('index') if isinstance(id_, dict) else None
        if not color or not color_values:
            continue

        selector = 'node'
        # build up selector by adding filters
        for condition in color_values:
            if isinstance(condition, str) and '=' in condition:
                # split up attribute value pairs
                attr, val = condition.split('=', 1)   # attr is normalized
                selector += f"[{attr}='{css_escape(val)}']"
        color_rules.append({
            'selector': selector,
            'style': {'border-color': color,}
        })

    return color_rules