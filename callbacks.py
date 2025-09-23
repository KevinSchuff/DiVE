from dash import Input, Output, State, ctx, no_update, ALL, dcc, html
import networkx as nx
import base64, csv, io, time
from urllib.parse import urlencode

from CSVHandler import load_graph_from_csv, normalize_key
from image_utils import bg_url_from_csv_value

# stylesheet generation
_css_esc = str.maketrans({"\\": r"\\\\", '"': r"\\\"", "'": r"\\'", "]": r"\\]", "[": r"\\["})
# make string safe to embed inside cytoscape attribute selector
def css_escape(s: str) -> str:
    return str(s).translate(_css_esc)

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
                G.add_edge(u_id, v_id, attr='same_front')
            elif mode == 'back' and back_u and back_u == back_v:
                G.add_edge(u_id, v_id, attr='same_back')
            elif mode == 'both' and front_u and back_u and front_u == front_v and back_u == back_v:
                G.add_edge(u_id, v_id, attr='same_front_back')

def create_dies_graph(coin_graph, front_col, back_col, front_url_col=None, back_url_col=None):
    """
    Build the die-view graph (one node per die). 
    - For image fields:
        * Absolute URLs -> proxified via /img_proxy
        * Relative paths -> served from /assets/...
    """
    die_graph = nx.Graph()
    # go through all nodes in coin_graph
    for node_id, data in coin_graph.nodes(data=True):
        coin_id = str(node_id)
        front_die = data.get(front_col)
        back_die = data.get(back_col)
        # add coin's back die, to die graph
        if front_die:
            if front_die not in die_graph:
                die_graph.add_node(front_die, typ=front_col, coin_ids=set())
            die_graph.nodes[front_die]["coin_ids"].add(coin_id)
            # assign image once if available
            if front_url_col and data.get(front_url_col) and "bg_url" not in die_graph.nodes[front_die]:
                bg = bg_url_from_csv_value(data.get(front_url_col))
                if bg:
                    die_graph.nodes[front_die]["bg_url"] = bg
        # add coin's back die to die grpah
        if back_die:
            if back_die not in die_graph:
                die_graph.add_node(back_die, typ=back_col, coin_ids=set())
            die_graph.nodes[back_die]["coin_ids"].add(coin_id)
            # assign image once if available
            if back_url_col and data.get(back_url_col) and "bg_url" not in die_graph.nodes[back_die]:
                bg = bg_url_from_csv_value(data.get(back_url_col))
                if bg:
                    die_graph.nodes[back_die]["bg_url"] = bg

        # connect front <-> back with weight
        if front_die and back_die:
            if die_graph.has_edge(front_die, back_die):
                die_graph[front_die][back_die]['weight'] += 1
            else:
                die_graph.add_edge(front_die, back_die, weight=1)

    for n in die_graph.nodes:
        die_graph.nodes[n]["coin_ids"] = sorted(die_graph.nodes[n]["coin_ids"])

    return die_graph


def nx_to_elements(G: nx.Graph):
    """
    Convert NetworkX graph into dash cytoscape elements list
    """
    elements = []
    for n, d in G.nodes(data=True):
        elements.append({'data': {'id': str(n), 'label': str(n), **d}})
    for u, v, ed in G.edges(data=True):
        e = {'data': {'source': str(u), 'target': str(v)}}
        if 'weight' in ed:
            e['data']['weight'] = ed['weight']
        elements.append(e)
    return elements

def base_stylesheet_dies():
    return [
        {'selector': 'node', 'style': {'label': 'data(label)'}},
        {
            'selector': 'edge',
            'style': {
                'label': 'data(weight)',
                'font-size': 12,
                'min-zoomed-font-size': 8,
                'text-rotation': 'autorotate',
                'line-color': 'black',
                'line-opacity': 0.7,
                'text-margin-y': -10
            }
        },
        {
            'selector': 'node[bg_url]', # nur wenn es eine bg_url gibt
            'style': {
                'background-image': 'data(bg_url)',
                'background-fit': 'cover',
                'background-opacity': 1,
                'width': 200,
                'height': 200,
                'border-width': 2,
                'border-color': '#444',
                'text-background-color': '#ffffff',
                'text-background-opacity': 0.5,
                'text-background-shape': 'round-rectangle'
            }
        }
    ]


def base_stylesheet_coins(edge_mode='front'):
    """
    Build the Cytoscape stylesheet for the coin-view.
    """
    styles = [
        {'selector': 'node', 'style': {'label': 'data(label)', 'width': 200, 'height': 200,'border-width': 2,}},
        {'selector': 'edge', 'style': {'line-color': 'black', 'line-opacity': 0.5}},
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


def color_and_filter_rules(color_values_list, color_ids, filter_store):
    """
    Helper to build cytoscape stylesheet rules
    """
    rules = []
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
        rules.append({
            'selector': selector,
            'style': {'border-color': color, 'border-width': 3, 'border-style': 'solid'}
        })

    # hide rules (attr names normalized)
    if isinstance(filter_store, dict):
        for attr, values in filter_store.items():
            for val in values or []:
                rules.append({
                    'selector': f"node[{attr}='{css_escape(val)}']",
                    'style': {'display': 'none'}
                })
    return rules

def build_layout(name: str):
    # https://js.cytoscape.org/#layouts
    # Link to extra layouts https://dash.plotly.com/cytoscape/layout
    layout = {'name': name, 'fit': True, 'padding': 30}

    if name == 'concentric':
        layout.update({'minNodeSpacing': 30})

    elif name == 'grid':
        layout.update({'avoidOverlap': True})

    elif name == 'circle':
        layout.update({'avoidOverlap': True})

    elif name == 'cose':
        layout.update({})

    elif name == 'cose-bilkent':
        layout.update({
            'randomize': False,
            'idealEdgeLength': 240,
            'edgeElasticity': 0.45,
            'nodeRepulsion': 12000,
            'nestingFactor': 0.1,
            'gravity': 0.25,
            'numIter': 2500,
            'tile': True,
            'tilingPaddingVertical': 20,
            'tilingPaddingHorizontal': 20,
            'gravityRange': 3.8,
            'gravityCompound': 1.0,
            'gravityRangeCompound': 3.0,
            'animate': False,
        })
    # needs fix : first preset, than apply layout
    elif name == 'cola':
        layout.update({
            'randomize': False,
            'avoidOverlap': True,
            'nodeSpacing': 16,      # smaller -> components can sit closer
            'edgeLength': 240,      # slightly shorter springs
            'maxSimulationTime': 2000,
            'infinite': False,           # keep the simulation alive
            'animate': True,
        })
    elif name == 'dagre':
        layout.update({
            'rankDir': 'LR',          # LR (left→right) or TB (top→bottom)
            'rankSep': 180,           # separation between ranks (rows and columns)
            'nodeSep': 60,            # separation within a rank
            'edgeSep': 20,
            'ranker': 'network-simplex',
            'animate': False,
        })

    elif name == 'klay':
        layout.update({
            'animate': False,
            'klay': {
                'direction': 'RIGHT',        # RIGHT, DOWN, LEFT, UP
                'nodePlacement': 'LINEAR_SEGMENTS',
                'edgeRouting': 'ORTHOGONAL', 
                'spacing': 60,               
                'borderSpacing': 20,
                'crossingMinimization': 'LAYER_SWEEP',
            }
        })

    return layout

def register_callbacks(app):
    @app.callback(
        Output('graph-store-coins', 'data', allow_duplicate=True),
        Output('elements-coins-base', 'data', allow_duplicate=True),
        Input('edge-mode', 'value'),
        State('graph-store-coins', 'data'),
        State('front-column', 'value'),
        State('back-column', 'value'),
        prevent_initial_call=True
    )
    def rebuild_edges_on_mode_change(edge_mode, graph_data_coins, col_front, col_back):
        """
        Deletes all existing edges in Graph and adds new edges based on selected edge mode
        """
        if not graph_data_coins:
            return no_update, no_update

        # Load the stored graph
        G = nx.readwrite.json_graph.node_link_graph(graph_data_coins)
        # Remove all existing edges and rebuild according to radio selection
        G.remove_edges_from(G.edges())
        front_key = normalize_key(col_front or "Stempeluntergruppe Av")
        back_key = normalize_key(col_back or "Stempeluntergruppe Rv")
        add_edges_by_mode(G, front_key, back_key, edge_mode)

        base_el = nx_to_elements(G)

        # Update the store (so stats/components recompute) and refresh coin-view elements
        return nx.readwrite.json_graph.node_link_data(G), base_el

    @app.callback(
        Output('elements-coins', 'data'),
        Input('elements-coins-base', 'data'),
        State('graph-store-coins', 'data'),
        State('front-column-url', 'value'),
        State('back-column-url', 'value'),
        prevent_initial_call=True
    )
    def enrich_images(base_elements, graph_data_coins, front_img_col, back_img_col):
        """
        adds images URLs to Cytoscape nodes
        """
        if not base_elements or not graph_data_coins:
            return no_update

        # get images column names
        front_img_col_norm = normalize_key(front_img_col or "Vorderseite Bild")
        back_img_col_norm = normalize_key(back_img_col or "Rueckseite Bild")

        # Rebuild graph to access node attributes
        G = nx.readwrite.json_graph.node_link_graph(graph_data_coins)

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


    @app.callback(
        Output('cy-coins', 'elements'),
        Input('elements-coins', 'data'),
    )
    def push_to_cytoscape(elements):
        return elements or []


    @app.callback(
        Output('layout-choices', 'data'),
        Input('layout-selector', 'value'),
        State('graph-view-selector', 'value'),
        State('layout-choices', 'data'),
    )
    def remember_layout_choice(selected, active_view, choices):
        choices = choices or {}
        choices[active_view] = selected
        return choices
    
    # when switching vies, the dropdown updates to stored layout
    @app.callback(
        Output('layout-selector', 'value'),
        Input('graph-view-selector', 'value'),
        State('layout-choices', 'data'),
    )
    def sync_dropdown_to_view(active_view, choices):
        choices = choices or {}
        return choices.get(active_view, 'grid')


    @app.callback(
        Output('custom-colors-store', 'data'),
        Input('add-color-button', 'n_clicks'),
        State('new-color-input', 'value'),
        State('custom-colors-store', 'data'),
        prevent_initial_call=True
    )
    def add_custom_color(n_clicks, color_input, color_list):
        if not color_input or color_input in color_list:
            return color_list
        return color_list + [color_input]

    @app.callback(
        Output('custom-color-dropdowns', 'children'),
        Input('custom-colors-store', 'data'),
        Input('graph-store-coins', 'data'),
        Input('graph-store-dies', 'data'),
        State('graph-view-selector', 'value')
    )
    def render_custom_color_dropdowns(colors, coins_data, dies_data, view):
        if not colors:
            return []

        graph_data = coins_data if view == 'coins' else dies_data
        if not graph_data:
            return []

        G = nx.readwrite.json_graph.node_link_graph(graph_data)
        combinations = set()
        for _, data in G.nodes(data=True):
            for k, v in data.items():
                if v is not None:
                    combinations.add(f"{k}={v}")
        options = [{'label': c, 'value': c} for c in sorted(combinations)]

        return [
            html.Div([
                html.Label(f"Color {color}:"),
                dcc.Dropdown(
                    id={'type': 'color-dropdown', 'index': color},
                    options=options,
                    multi=True,
                    searchable=True
                )
            ], style={'marginBottom': '10px'}) for color in colors
        ]

    @app.callback(
        Output('filter-values-store', 'data'),
        Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        Input('upload-data', 'contents'),
        State({'type': 'filter-dropdown', 'index': ALL}, 'id'),
        prevent_initial_call=True
    )
    def collect_filter_values(values_list, upload_contents, ids):
        """
        Collect current selection of all filtr dropdowns and store them in a dict
        """
        # if upload triggered -> empty store
        if ctx.triggered_id == 'upload-data':
            return {}

        # no filter dropdowns avail
        if not ids:
            return {}
        # build dict like {attribute name: [values...]}
        result = {}
        for vaulues, dropdown_id in zip(values_list, ids):
            if vaulues:  
                result[dropdown_id['index']] = [str(v) for v in vaulues]
        return result or {}


    @app.callback(
        Output('csv-approved', 'data'),
        Output('pending-csv', 'data'),
        Output('csv-size-warning', 'displayed'),            
        Input('upload-data', 'contents'),                       
        Input('csv-size-warning', 'submit_n_clicks'),           # OK button
        Input('csv-size-warning', 'cancel_n_clicks'),           # Cancel button
        State('pending-csv', 'data'),
        prevent_initial_call=True
    )
    def gate_and_decide(contents, ok_clicks, cancel_clicks, pending):
        """
        gatekeeps larger csv. if it is < 100 rows accept immediately, else stash in pending-csv and show dialogue box
        """
        # check which input triggered
        trig = ctx.triggered_id

        # csv was uploaded -> count lines and decide to show dialogue box
        if trig == 'upload-data' and contents:
            content_type, content_string = contents.split(',', 1)
            decoded = base64.b64decode(content_string)
            text = decoded.decode('latin-1', errors='ignore')

            #count rows
            f = io.StringIO(text)
            reader = csv.reader(f)
            header = next(reader, None)
            n_rows = sum(1 for _ in reader)

            if n_rows <= 100:
                return contents, None, False
            else:
                return None, contents, True

        # user clicked OK in dialogue box -> use full csv
        if trig == 'csv-size-warning' and ok_clicks:
            if pending:
                return pending, None, False
            return no_update, None, False

        # user clicked Cancel in dialogue box -> use first 100 lines
        if trig == 'csv-size-warning' and (cancel_clicks is not None):
            if not pending:
                return no_update, None, False
            # decode pending csv
            content_type, content_string = pending.split(',', 1)
            decoded = base64.b64decode(content_string)
            text = decoded.decode('latin-1', errors='ignore')
            # only keep first 100 lines
            fin = io.StringIO(text)
            reader = csv.reader(fin)
            header = next(reader, [])
            rows = []
            for i, row in enumerate(reader):
                if i >= 100:
                    break
                rows.append(row)
            # re-encode the reduced csv 
            fout = io.StringIO()
            w = csv.writer(fout, lineterminator='\n')
            if header:
                w.writerow(header)
            w.writerows(rows)
            reduced_text = fout.getvalue().encode('latin-1', errors='ignore')
            reduced_b64 = base64.b64encode(reduced_text).decode('ascii')
            reduced_contents = f"data:text/csv;base64,{reduced_b64}"

            return reduced_contents, None, False

        return no_update, no_update, False


    """
    @app.callback(
        Output('zip-file-list', 'data'),
        Output('zip-status', 'children'),
        Input('upload-zip', 'contents'),
        State('upload-zip', 'filename'),
        prevent_initial_call=True
    )
    def handle_zip_upload(contents, filename):
        global ZIP_IMAGE_STORE
        if not contents:
            return no_update, no_update
        try:
            content_type, content_string = contents.split(',', 1)
            decoded = base64.b64decode(content_string)
            with zipfile.ZipFile(io.BytesIO(decoded)) as z:
                ZIP_IMAGE_STORE.clear()
                count = 0
                files = []
                for name in z.namelist():
                    if name.endswith('/'):
                        continue
                    key = norm_path(name)
                    ZIP_IMAGE_STORE[key] = z.read(name)
                    files.append(key)
                    count += 1
            status = f"ZIP ready ({filename}): {count} files available."
            return files, status
        except Exception as e:
            return [], f"Error loading ZIP: {e}"
    """
        
    @app.callback(
        Output('graph-store-coins', 'data'),
        Output('graph-store-dies', 'data'),
        Output('elements-coins-base', 'data'),
        Output('elements-dies', 'data'),
        Output('cy-dies', 'elements'),
        Output('filter-dropdowns', 'children'),
        Output({'type': 'color-dropdown', 'index': 'red'}, 'options'),
        Output({'type': 'color-dropdown', 'index': 'blue'}, 'options'),
        Output({'type': 'color-dropdown', 'index': 'green'}, 'options'),
        Input('csv-approved', 'data'),
        State('front-column', 'value'),
        State('back-column', 'value'),
        State('front-column-url', 'value'),
        State('back-column-url', 'value'),
        State('edge-mode', 'value'),
    )
    def handle_file_upload(contents, col_front, col_back, col_front_url, col_back_url, edge_mode):
        """
        Decodes CSV and builds coin graph and die graph. prepares filter und color options UI
        """
        if not contents:
            return (no_update, no_update, no_update, no_update,
                    no_update, [], [], [], [])
        
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        G = load_graph_from_csv(decoded)

        # Normalize the user-provided (or default) column names
        front_key = normalize_key(col_front or "Stempeluntergruppe Av")
        back_key = normalize_key(col_back or "Stempeluntergruppe Rv")
        front_url_key = normalize_key(col_front_url or "Vorderseite Bild")
        back_url_key = normalize_key(col_back_url or "Rueckseite Bild")

        # build edges according to selected mode
        add_edges_by_mode(G, front_key, back_key, edge_mode)

        # {attribute -> {values}} for filter dropdown
        attribute_values = dict()
        #set of "attribute=value" strings for color dropdown
        combinations = set()
        for _, data in G.nodes(data=True):
            for attribute, value in data.items():
                if value is not None:
                    attribute_values.setdefault(attribute, set()).add(value)
                    combinations.add(f"{attribute}={value}")

        # build filter dropdown for every attribute
        filter_ui = [
            html.Div([
                html.Label(f"{attr}"),
                dcc.Dropdown(
                    id={'type': 'filter-dropdown', 'index': attr},
                    options=[{'label': str(val), 'value': str(val)} for val in sorted(vals)],
                    multi=True,
                    searchable=True,
                    placeholder=f"Search {attr} value",
                    style={'margin-bottom': '10px'}
                )
            ])
            for attr, vals in attribute_values.items()
        ]

        options = [{'label': c, 'value': c} for c in sorted(combinations)]

        # build die-graph with input columns
        dies_graph = create_dies_graph(
            G, front_col=front_key, back_col=back_key,
            front_url_col=front_url_key, back_url_col=back_url_key
            )

        # cytoscape elements for graphs
        coins_base_el = nx_to_elements(G)             # base (no images)
        dies_el = nx_to_elements(dies_graph)

        return (
            nx.readwrite.json_graph.node_link_data(G),
            nx.readwrite.json_graph.node_link_data(dies_graph),
            coins_base_el,
            dies_el,
            dies_el,
            filter_ui,
            options,
            options,
            options
        )

    # Toggle which Cytoscape is visible (keep both mounted)
    @app.callback(
        Output('cy-coins', 'style'),
        Output('cy-dies', 'style'),
        Input('graph-view-selector', 'value'),
        )
    def toggle_visible_view(view):
        base = {'width': '100%', 'height': '800px'}
        if view == 'dies':
            return {**base, 'display': 'none'}, {**base, 'display': 'block'}
        return {**base, 'display': 'block'}, {**base, 'display': 'none'}




    @app.callback(
        Output('cy-coins', 'stylesheet'),
        Output('cy-dies', 'stylesheet'),
        Output('stats-box', 'children'),
        Input('graph-view-selector', 'value'),
        Input({'type': 'color-dropdown', 'index': ALL}, 'value'),
        Input('filter-values-store', 'data'),
        Input('edge-mode', 'value'),
        State({'type': 'color-dropdown', 'index': ALL}, 'id'),
        State('graph-store-coins', 'data'),
        State('graph-store-dies', 'data'),
        State('front-column', 'value'),
        State('back-column', 'value'),
    )
    def update_styles_and_stats(view, color_values_list, filter_store, edge_mode, color_ids,
                                graph_data_coins, graph_data_dies, col_front, col_back):
        """
        Updates stylesheets and stat box on change of view, color , filter or edge mode selection
        """
        if not graph_data_coins:
            return no_update, no_update, no_update
        # build stylesheet rules for both views
        stylesheet_common = color_and_filter_rules(color_values_list, color_ids, filter_store)

        # append basestylesheets
        ss_coins = base_stylesheet_coins(edge_mode) + stylesheet_common
        ss_dies = base_stylesheet_dies() + stylesheet_common

        # --- Stats (exact, computed in Python; does not change elements) ---
        G_coins_full = nx.readwrite.json_graph.node_link_graph(graph_data_coins)

        # Apply filters to compute visible coins
        hidden = set()
        if filter_store:
            for attr, values in filter_store.items():
                for n, d in G_coins_full.nodes(data=True):
                    if attr in d and str(d[attr]) in values:
                        hidden.add(n)
        visible_coins = [n for n in G_coins_full.nodes if n not in hidden]
        G_coins_visible = G_coins_full.subgraph(visible_coins).copy()
        count_coins = G_coins_visible.number_of_nodes()

        front_key = normalize_key(col_front or "Stempeluntergruppe Av")
        back_key = normalize_key(col_back or "Stempeluntergruppe Rv")

        if view == 'coins':
            vis_nodes_data = list(G_coins_visible.nodes(data=True))
            all_dies = (
                {str(d.get(front_key)) for _, d in vis_nodes_data if d.get(front_key)}
                | {str(d.get(back_key)) for _, d in vis_nodes_data if d.get(back_key)}
            )
            dies_visible = len(all_dies)
            components = nx.number_connected_components(G_coins_visible) if count_coins else 0
        else:
        # CHANGE: this should be changed so if coin nodes get filtered, the corresponding die should be filtered aswell?
        # currently creates seperate die graph only for stats
            die_graph = create_dies_graph(G_coins_visible, front_col=front_key, back_col=back_key)
            dies_visible = die_graph.number_of_nodes()
            components = nx.number_connected_components(die_graph) if dies_visible else 0

        def _stats_list(items):
            return html.Ul([html.Li(it) for it in items], style={'margin': 0, 'paddingLeft': '18px'})

        stats_children = html.Div([
            _stats_list([
                f"Coins: {count_coins}",
                f"Dies: {dies_visible}",
                f"Connected components: {components}",
            ])
        ])

        return ss_coins, ss_dies, stats_children

    @app.callback(
        Output('lightbox', 'style'),
        Output('lightbox-img', 'src'),
        Input('cy-coins', 'tapNodeData'),
        Input('cy-dies', 'tapNodeData'),
        Input('lightbox-close', 'n_clicks'),
        State('edge-mode', 'value'),
        prevent_initial_call=True
    )
    def open_lightbox_on_left_click(data_m, data_s, close_clicks, edge_mode):
        # Close button clicked -> hide overlay
        if ctx.triggered_id == 'lightbox-close':
            return {'display': 'none'}, no_update

        # Which Cytoscape fired
        data = data_m or data_s
        if not data:
            return {'display': 'none'}, no_update

        # Decide which image URL to show
        url = None
        if 'bg_url' in data:  # die-view node
            url = data.get('bg_url')
        elif edge_mode == 'front':
            url = data.get('bg_front')
        elif edge_mode == 'back':
            url = data.get('bg_back')
        else:  # both
            f= data.get('bg_front')
            b = data.get('bg_back')
            if f and b:
                # instead of just getting the bg_split, we create a higher resolution picture
                url = f"/merge_split?{urlencode({'w': 1000, 'h': 1000, 'front': f, 'back': b})}"
            else:
                url = f or b

        if not url:
            return {'display': 'none'}, no_update

        overlay_style = {
            'display': 'flex',
            'position': 'fixed', 'inset': 0,
            'background': 'rgba(0,0,0,0.6)',
            'zIndex': 9999, 'justifyContent': 'center', 'alignItems': 'center',
            'padding': '24px'
        }
        return overlay_style, url


    @app.callback(
        Output('node-info-box', 'children'),
        Input('cy-coins', 'mouseoverNodeData'),
        Input('cy-dies', 'mouseoverNodeData')
    )
    def display_node_data(data_m, data_s):
        # Use whichever graph actually triggered
        trig = ctx.triggered_id
        if trig == 'cy-dies':
            data = data_s
        elif trig == 'cy-coins':
            data = data_m
        else:
            data = data_s or data_m

        if not data:
            return "Hover over a node to see details"

        label = data.get('label', 'untitled')
        # only show attributes in the csv
        skip_keys = {'id', 'label', 'bg_front', 'bg_back', 'bg_split', 'timeStamp', 'bg_url'}
        items = []
        for k, v in data.items():
            if k in skip_keys:
                continue
            items.append(html.Li([html.Strong(f"{k}: "), str(v)]))

        return html.Div([
            html.H4(f"Node: {label}"),
            html.Ul(items, style={'margin': 0, 'paddingLeft': '18px'})
        ])





    @app.callback(
        Output('cy-coins', 'layout'),
        Output('cy-dies', 'layout'),
        Output('dies-force-grid-once', 'data'),
        Input('layout-selector', 'value'),
        Input('graph-view-selector', 'value'),
        Input('dies-force-grid-once', 'data'),
    )
    def set_layout(selected, active_view, force_once):
        layout = build_layout(selected)
        # fix for die-view not having a layout applied on first switch
        if active_view == 'dies' and force_once==True:
            # add same for switched cases
            time.sleep(1)
            return no_update, layout, False

        if active_view == 'coins':
            return layout, no_update, force_once
        else:
            return no_update, layout, force_once

    @app.callback(
        Output('cy-coins', 'generateImage'),
        Output('cy-dies', 'generateImage'),
        Input('export-png-button', 'n_clicks'),
        State('graph-view-selector', 'value'),
        prevent_initial_call=True
    )
    def export_png(n_clicks, view):
        if view == 'dies':
            return no_update, {
                'type': 'png',
                'action': 'download',
                'filename': 'diesgraph_view',
                'full': False,
                'scale': 1,
                'bg': 'white'
            }
        else:
            return {
                'type': 'png',
                'action': 'download',
                'filename': 'coingraph_view',
                'full': False,
                'scale': 1,
                'bg': 'white'
            }, no_update
