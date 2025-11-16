from dash import Input, Output, State, ctx, no_update, ALL, dcc, html
import networkx as nx
from CSVHandler import normalize_key
from graph_handler import remove_duplicate_dies, add_edges_by_mode, create_dies_graph, nx_to_elements
from layouts import build_layout
from styles import base_stylesheet_coins, base_stylesheet_dies, set_hiding_rules, set_color_rules


def register_update_view_callbacks(app):
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
        Output('cy-coins', 'elements'),
        Input('elements-coins', 'data'),
    )
    def push_to_cytoscape(elements):
        return elements or []


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


    # Toggle which Cytoscape is visible (keep both mounted)
    @app.callback(
        Output('cy-coins', 'style'),
        Output('cy-dies', 'style'),
        Output('scale-weighted-edges-container', 'style'),
        Output('edge-mode-container', 'style'),
        Output('color-nodes-container', 'style'),
        Input('graph-view-selector', 'value'),
        )
    def toggle_visible_view(view):
        base = {'width': '100%', 'height': '100%'}
        if view == 'dies':
            return {**base, 'display': 'none'}, {**base, 'display': 'block'}, {'display': 'block'}, {'display': 'none'}, {'display': 'none'}
        else:
            return {**base, 'display': 'block'}, {**base, 'display': 'none'}, {'display': 'none'}, {'display': 'block'}, {'display': 'block'}


    @app.callback(
        Output('cy-coins', 'stylesheet'),
        Output('cy-dies', 'stylesheet'),
        Output('stats-box', 'children'),
        Output('cy-dies', 'elements', allow_duplicate=True),
        Output('hidden-store', 'data'),
        Input('show-only-selection-button', 'n_clicks'),
        Input('hide-selection-button', 'n_clicks'),
        Input('reset-selection-button', 'n_clicks'),
        Input('graph-view-selector', 'value'),
        Input({'type': 'color-dropdown', 'index': ALL}, 'value'),
        Input('filter-values-store', 'data'),
        Input('edge-mode', 'value'),
        Input('scale-weighted-edges', 'value'),
        State({'type': 'color-dropdown', 'index': ALL}, 'id'),
        State('graph-store-coins', 'data'),
        State('graph-store-dies', 'data'),
        State('front-column', 'value'),
        State('back-column', 'value'),
        State('front-column-url', 'value'),
        State('back-column-url', 'value'),
        State('cy-coins', 'selectedNodeData'),
        State('cy-dies', 'selectedNodeData'),
        State('hidden-store', 'data'),
        State('cy-dies', 'elements'),   
        prevent_initial_call=True
    )
    def update_styles_and_stats(show_click, hide_click, unhide_click, view, color_values_list, filter_store, edge_mode, scale_weighted_edges, color_ids,
                                graph_data_coins, graph_data_dies, col_front, col_back, col_front_url, col_back_url, selected_nodes_coins,
                                selected_nodes_dies, hidden, dies_elements_current):
        """
        Updates stylesheets and stat box on change of view, color , filter or edge mode selection
        """
        if not graph_data_coins:
            return no_update, no_update, no_update, no_update, no_update
        
        G_coins_full = nx.readwrite.json_graph.node_link_graph(graph_data_coins)
        # prepare column names
        front_key = normalize_key(col_front or "Stempeluntergruppe Av")
        back_key = normalize_key(col_back or "Stempeluntergruppe Rv")
        front_url_key = normalize_key(col_front_url or "Vorderseite Bild")
        back_url_key = normalize_key(col_back_url or "Rueckseite Bild")

        # apply attribute based filter
        hide_nodes_attr = set()
        if filter_store:
            for attr, values in filter_store.items():
                for n, d in G_coins_full.nodes(data=True):
                    if attr in d and str(d[attr]) in values:
                        hide_nodes_attr.add(n)
        visible_coins = [n for n in G_coins_full.nodes if n not in hide_nodes_attr]
        G_coins_visible = G_coins_full.subgraph(visible_coins).copy()
        
        # get stored hidden coin ids and dies
        hidden_store = hidden or {}
        hidden_store_coins = hidden_store.get("coins", []) # list of coin ids (str)
        hidden_store_dies = hidden_store.get("dies", [])  # list of die obj like {"id":, .., "typ":, ...,}

        # Decide what coins/dies to hide
        # Case1: "Unhide Selection" was clicked -> reset everything that is selection-based
        if ctx.triggered_id == "reset-selection-button":
            all_hidden_coins_ids = set()
            all_hidden_dies_objs = []
        # Case2: "Hide Selection" was clicked -> extend hidden stores with current selection
        elif ctx.triggered_id == "hide-selection-button":
            # add current selection of current view to hidden store
            if view == 'coins':
                selection_ids = [str(d["id"]) for d in (selected_nodes_coins or []) if isinstance(d, dict) and "id" in d]
                all_hidden_coins_ids = set(hidden_store_coins + selection_ids) #make to list?
                all_hidden_dies_objs = hidden_store_dies
            else: 
                selection_dies = [{"id": str(d["id"]), "typ": d.get("typ")} for d in (selected_nodes_dies or [])if isinstance(d, dict) and "id" in d]
                all_hidden_dies_objs = remove_duplicate_dies(hidden_store_dies + selection_dies)
                all_hidden_coins_ids = set(hidden_store_coins) #make to list?
        # Case3: "Show only Selection" was clicked -> extend hidden stores with everything but the current selection
        elif ctx.triggered_id == "show-only-selection-button":
            if view == 'coins':
                # nodes currently visible after attribute-based filter
                visible_coin_ids = {str(n) for n in G_coins_visible.nodes}
                selection_ids = {str(d["id"]) for d in (selected_nodes_coins or []) if isinstance(d, dict) and "id" in d}
                not_selected_coins = visible_coin_ids - selection_ids
                # set union of store and not selected coins
                all_hidden_coins_ids = set(hidden_store_coins) | not_selected_coins
                all_hidden_dies_objs = hidden_store_dies
            else:
                # get die ids from current selection
                visible_die_ids = {
                    str(el.get("data", {}).get("id")) 
                    for el in (dies_elements_current or [])
                        if "id" in el.get("data", {})   # check if element is node
                    }
                selection_ids = {str(d["id"]) for d in (selected_nodes_dies or []) if isinstance(d, dict) and "id" in d}
                not_selected_dies_ids = visible_die_ids - selection_ids
                # convert to dies obj with id and typ
                new_hidden_dies_obj = []
                # get not selected dies typ
                for el in (dies_elements_current or []):
                    if "id" in el.get("data", {}):
                        data = el.get("data", {})
                        node_id = str(data.get("id"))
                        if node_id in not_selected_dies_ids:
                            new_hidden_dies_obj.append({"id": node_id, "typ": data.get("typ")})
                all_hidden_dies_objs = remove_duplicate_dies(hidden_store_dies + new_hidden_dies_obj)
                all_hidden_coins_ids = set(hidden_store_coins)
        # Case3: view change, attribute filter, colors or edgemode triggered the callback -> use only hidden store 
        else:
            all_hidden_coins_ids = set(hidden_store_coins)
            all_hidden_dies_objs = hidden_store_dies
        
        # rebuild die-graph without hidden coins/dies (attribute based filtering + selection based)
        all_hidden_dies_ids = [d["id"] for d in all_hidden_dies_objs]
        updated_die_graph, biggest_edge_weight = create_dies_graph(G_coins_visible, front_key, back_key, all_hidden_coins_ids, all_hidden_dies_ids, front_url_key, back_url_key)

        # build stylesheet rules for both views
        color_rules = set_color_rules(color_values_list, color_ids)
        hiding_rules = set_hiding_rules(filter_store, all_hidden_coins_ids, all_hidden_dies_objs)
        # append basestylesheets
        ss_coins = base_stylesheet_coins(edge_mode) + color_rules + hiding_rules
        if 'on' in scale_weighted_edges:
            ss_dies = base_stylesheet_dies(True, biggest_edge_weight) + color_rules + hiding_rules
        else:
            ss_dies = base_stylesheet_dies(False) + color_rules + hiding_rules

        # compute stats
        count_coins = G_coins_visible.number_of_nodes() - len(all_hidden_coins_ids)
        count_dies = updated_die_graph.number_of_nodes()
        if view == 'coins':
            components = nx.number_connected_components(G_coins_visible) if count_coins else 0
        else:
            components = nx.number_connected_components(updated_die_graph) if count_dies else 0

        def _stats_list(items):
            return html.Ul([html.Li(it) for it in items], style={'margin': 0, 'paddingLeft': '18px'})

        stats_children = html.Div([
            _stats_list([
                f"Coins: {count_coins}",
                f"Dies: {count_dies}",
                f"Connected components: {components}",
            ])
        ])

        # update hidden store
        hidden_out = no_update
        if ctx.triggered_id in ('hide-selection-button', 'show-only-selection-button'):
            hidden_out = {
                "coins": sorted(all_hidden_coins_ids),
                "dies": all_hidden_dies_objs,
            }
        elif ctx.triggered_id == 'reset-selection-button':
            hidden_out = {
            "coins": [],
            "dies": [],
            }
        
                # --- Decide whether to actually update cy-dies.elements ---
        trigger = ctx.triggered_id

        structural_triggers = (
            'hide-selection-button',
            'reset-selection-button',
            'filter-values-store',
        )
        update_die_elements = trigger in structural_triggers
        

        if update_die_elements:
            die_elements_out = nx_to_elements(updated_die_graph)
        else:
            die_elements_out = no_update

        return ss_coins, ss_dies, stats_children, nx_to_elements(updated_die_graph), hidden_out


    @app.callback(
        Output('cy-coins', 'layout'),
        Output('cy-dies', 'layout'),
        Input('layout-selector', 'value'),
        State('graph-view-selector', 'value'),
        State('auto-layout-toggle', 'value'),
        prevent_initial_call=True
    )
    def set_layout(selected_layout, active_view, auto_layout_toggle):

        auto_enabled = 'on' in (auto_layout_toggle or [])
        layout = build_layout(selected_layout)

        # If auto-layout is off, only change layout on layout-selector
        if not auto_enabled:
            if ctx.triggered_id == 'layout-selector':
                        if active_view == 'coins':
                            return layout, no_update
                        elif active_view == 'dies':
                            return no_update, layout
            else:
                return no_update, no_update
        
        # Apply layout only to the currently active view
        if active_view == 'coins':
            return layout, no_update
        else:
            return no_update, layout