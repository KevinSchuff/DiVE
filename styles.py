# stylesheet generation
_css_esc = str.maketrans({"\\": r"\\\\", '"': r"\\\"", "'": r"\\'", "]": r"\\]", "[": r"\\["})
# make string safe to embed inside cytoscape attribute selector
def css_escape(s: str) -> str:
    return str(s).translate(_css_esc)

def base_stylesheet_dies(scale_edges_weight=False, max_edge_weight = 0):
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
    Build the Cytoscape stylesheet for the coin-view.
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

#MERGE remove both
    if edge_mode == 'front':
        styles.append(_img_rule('bg_front'))

    elif edge_mode == 'back':
        styles.append(_img_rule('bg_back'))
    else:
        # mode == 'both': lowest → highest priority (later wins)
        styles.append(_img_rule('bg_back'))   # fallback 3
        styles.append(_img_rule('bg_front'))  # fallback 2
        styles.append(_img_rule('bg_split'))  # preferred 1

    return styles


def set_hiding_rules(filter_store, skip_coins, skip_dies):
    """
    Helper to build cytoscape stylesheet rules for hiding specific nodes
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
    Helper to build cytoscape stylesheet rules
    """
    color_rules = []
    # color rules (attr names are normalized; values may have spaces/umlauts)
    for color_values, id_ in zip(color_values_list or [], color_ids or []):
        color = id_.get('index') if isinstance(id_, dict) else None
        if not color or not color_values:
            continue
        selector = 'node'
        for cond in color_values:
            if isinstance(cond, str) and '=' in cond:
                attr, val = cond.split('=', 1)   # attr is normalized
                selector += f"[{attr}='{css_escape(val)}']"
        color_rules.append({
            'selector': selector,
            'style': {'border-color': color,}
        })

    return color_rules