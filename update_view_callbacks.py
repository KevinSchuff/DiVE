"""
This module handles all callbacks, that are relevant for updating the cytoscape instances, this includes
edge rebuilding, filtering, coloring and layout changes for both coin- and die-view.
"""

from dash import Input, Output, State, ctx, no_update, ALL, dcc, html
import networkx as nx

from csv_handler import normalize_key
from graph_handler import remove_duplicate_dies, add_edges_by_mode, create_dies_graph, nx_to_elements, enrich_images
from layouts import build_layout
from styles import base_stylesheet_coins, base_stylesheet_dies, set_hiding_rules, set_color_rules


def register_update_view_callbacks(app):
    """
    Register all dash callbacks relevant to updating the cytoscape instances to the app.

    Parameters
    ----------
    app : dash.Dash
        Dash application instance to which the callbacks will be attached.
    """

    @app.callback(
        Output('graph-store-coins', 'data', allow_duplicate=True),
        Output('cy-coins', 'elements', allow_duplicate=True),
        Input('edge-mode', 'value'),
        State('graph-store-coins', 'data'),
        State('front-column', 'value'),
        State('back-column', 'value'),
        State('front-url-column', 'value'),
        State('back-url-column', 'value'),
        prevent_initial_call=True
    )
    def rebuild_edges_on_mode_change(edge_mode, graph_data_coins, front_column, back_column, front_url_column, back_url_column):
        """
        Rebuild edges in coin-view when the edge-mode changes.

        Parameters
        ----------
        edge_mode : str
            String contains currenty selected edge mode for coin-view. Is either front, back or both.
        graph_data_coins : dict or None
            stores graph, node and edge attributes from coins.
        front_column : str or None
            String inside inputfield with id 'front-column'. 
        back_column : str or None
            String inside inputfield with id 'back-column'
        front_url_column : str or None
            String inside inputfield with id 'front-url-column'
        back_url_column : str or None
            String inside inputfield with id 'back-url-column'

        Returns
        -------
        dict
            stores graph, node and edge attributes from coins.
        list of dict  
            element list of dash cytoscape instance cy-coins.
        """

        if not graph_data_coins:
            return no_update, no_update

        # Load the stored graph
        G = nx.readwrite.json_graph.node_link_graph(graph_data_coins)
        # Remove all existing edges and rebuild according to radio selection
        G.remove_edges_from(G.edges())

        front_key = normalize_key(front_column or "front die")
        back_key = normalize_key(back_column or "back die")
        front_url_key = normalize_key(front_url_column or "front img")
        back_url_key = normalize_key(back_url_column or "back img")

        add_edges_by_mode(G, front_key, back_key, edge_mode)

        # convert to elements
        coins_base_elements = nx_to_elements(G)
        coins_with_images_elements = enrich_images(G, coins_base_elements, front_url_key, back_url_key)

        return nx.readwrite.json_graph.node_link_data(G), coins_with_images_elements


    @app.callback(
        Output('filter-values-store', 'data'),
        Input({'type': 'filter-dropdown', 'index': ALL}, 'value'),
        Input('upload-data', 'contents'),
        State({'type': 'filter-dropdown', 'index': ALL}, 'id'),
        prevent_initial_call=True
    )
    def collect_filter_values(values_list, contents, ids):
        """
        Collects current selection of all filter dropdowns.

        Parameters
        ----------
        values_list : list of list
            List of selected values for each filter dropdown.
        contents : str or None
            base64 encoded string containing uploaded CSV file's content
        ids : list of dict
            List of dropdown component IDs, index key represents attribute name.

        Returns
        -------
        dict
            Mapping of attribute name to a list of selected values.
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
        Output('cy-coins', 'style'),
        Output('cy-dies', 'style'),
        Output('scale-weighted-edges-container', 'style'),
        Output('edge-mode-container', 'style'),
        Output('color-nodes-container', 'style'),
        Input('graph-view-selector', 'value'),
        )
    def toggle_visible_view(view):
        """
        Toggle visibility of coin- and die-view (cytoscape instances) and associated UI-controls.

        Parameters
        ----------
        view : str
            Currently selected view from the graph view selector.

        Returns
        -------
        dict
            Style for the coin Cytoscape instance.
        dict
            Style for the die Cytoscape instance.
        dict
            Style for the scale-weighted-edges container.
        dict
            Style for the edge-mode container.
        dict
            Style for the color-nodes container.
        """
         
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
        State('front-url-column', 'value'),
        State('back-url-column', 'value'),
        State('cy-coins', 'selectedNodeData'),
        State('cy-dies', 'selectedNodeData'),
        State('hidden-store', 'data'),
        State('cy-dies', 'elements'),   
        prevent_initial_call=True
    )
    def update_styles_and_stats(show_click, hide_click, unhide_click, view, color_values_list, filter_store,
                                edge_mode, scale_weighted_edges, color_ids, graph_data_coins, graph_data_dies,
                                front_column, back_column, front_url_column, back_url_column, selected_nodes_coins,
                                selected_nodes_dies, hidden, dies_elements_current):
        """
        Update die elementslist, coin- and die-stylsheet, statistics and hidden stores.
        This callback triggers upon any selection button, view change, changes in the dropdown's, changing edge options.

        Parameters
        ----------
        show_click : int or None
            Number of clicks on the 'show only selection' button.
        hide_click : int or None
            Number of clicks on the 'hide selection' button.
        unhide_click : int or None
            Number of clicks on the "reset selection" button.
        view : str
            Currently selected view from the graph view selector.
        color_values_list : list of list of str
            Each element in the list is a list of condition strings (looking like attr=value) for a particular color.
            Nodes with the logical conjuction of attribute values should be colored.
        filter_store : dict
            Mapping of attribute name to a list of selected values.
        edge_mode : str
            String contains currenty selected edge mode for coin-view. Is either front, back or both.
        scale_weighted_edges : list
            List contains 'on' if checklist is clicked, else empty.
        color_ids : list of dict
            IDs of the color-dropdown components (used to map to attributes).
        graph_data_coins : dict or None
            Stores graph, node and edge attributes from coins.
        graph_data_dies : dict or None
            Stores graph, node and edge attributes from dies.
        front_column : str or None
            Text in 'front-column' input fields.
        back_column : str or None
            Text in 'front-column' input fields.
        front_url_column : str or None
            Text in 'front-url-column' input fields.
        back_url_column : str or None
            Text in 'back-url-column' input fields.
        selected_nodes_coins : list of dict or None
            Selected nodes in the coin cytoscape instance.
        selected_nodes_dies : list of dict or None
            Selected nodes in the die cytoscape instance.
        hidden : dict or None
            Previously stored hidden coin and die information.
        dies_elements_current : list of dict or None
            Current elementlist from die cytoscape instance.

        Returns
        -------
        list of dict
            Stylesheet for the coin cytoscape instance.
        list of dict
            Stylesheet for the die cytoscape instance.
        dash.html.Div
            Children for the stats box, containing statistics.
        list of dict
            Elementlist from die cytoscape instance after updating.
        dict
            Updated stored hidden coin and die information.
        """
        # if no coin graph exists yet, nothing can be updated
        if not graph_data_coins:
            return no_update, no_update, no_update, no_update, no_update
        # rebuild networkX graph from stored graph structure
        coin_graph_full = nx.readwrite.json_graph.node_link_graph(graph_data_coins)
        # prepare column names
        front_key = normalize_key(front_column or "front die")
        back_key = normalize_key(back_column or "back die")
        front_url_key = normalize_key(front_url_column or "front img")
        back_url_key = normalize_key(back_url_column or "back img")

        # apply attribute based filter to coin graph
        hide_nodes_by_attr = set()
        if filter_store:
            for attr, values in filter_store.items():
                for node_id, node_data in coin_graph_full.nodes(data=True):
                    if attr in node_data and str(node_data[attr]) in values:
                        hide_nodes_by_attr.add(node_id)
        visible_coins = [node_id for node_id in coin_graph_full.nodes if node_id not in hide_nodes_by_attr]
        coin_graph_filtered = coin_graph_full.subgraph(visible_coins).copy()
        
        # get stored hidden coin ids and dies
        hidden_store = hidden or {}
        hidden_store_coins = hidden_store.get("coins", []) # list of coin ids (str)
        hidden_store_dies = hidden_store.get("dies", [])  # list of die obj like {"id":, .., "typ":, ...,}

        # Decide what coins/dies to hide
        # Case 1: "Unhide Selection" was clicked -> reset everything that is selection-based
        if ctx.triggered_id == "reset-selection-button":
            all_hidden_coins_ids = set()
            all_hidden_dies_objs = []
        # Case 2: "Hide Selection" was clicked -> extend hidden stores with current selection
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
        # Case 3: "Show only Selection" was clicked -> extend hidden stores with everything but the current selection
        elif ctx.triggered_id == "show-only-selection-button":
            if view == 'coins':
                # nodes currently visible after attribute-based filter
                visible_coin_ids = {str(n) for n in coin_graph_filtered.nodes}
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
                # build die objects for all not selected dies, that now should be hidden
                for el in (dies_elements_current or []):
                    if "id" in el.get("data", {}):
                        data = el.get("data", {})
                        node_id = str(data.get("id"))
                        if node_id in not_selected_dies_ids:
                            new_hidden_dies_obj.append({"id": node_id, "typ": data.get("typ")})
                all_hidden_dies_objs = remove_duplicate_dies(hidden_store_dies + new_hidden_dies_obj)
                all_hidden_coins_ids = set(hidden_store_coins)
        # Case4: Any other trigger (view change, attribute filter, colors or edgemode) triggered the callback -> use only hidden store 
        else:
            all_hidden_coins_ids = set(hidden_store_coins)
            all_hidden_dies_objs = hidden_store_dies
        
        # rebuild die-graph without hidden coins/dies (attribute based filtering + selection based)
        all_hidden_dies_ids = [d["id"] for d in all_hidden_dies_objs]
        updated_die_graph, biggest_edge_weight = create_dies_graph(coin_graph_filtered, front_key, back_key, all_hidden_coins_ids, all_hidden_dies_ids, front_url_key, back_url_key)

        # build stylesheet rules for both views
        color_rules = set_color_rules(color_values_list, color_ids)
        hiding_rules = set_hiding_rules(filter_store, all_hidden_coins_ids, all_hidden_dies_objs)
        # append basestylesheets
        stylesheet_coins = base_stylesheet_coins(edge_mode) + color_rules + hiding_rules
        if 'on' in scale_weighted_edges:
            stylesheet_dies = base_stylesheet_dies(True, biggest_edge_weight) + color_rules + hiding_rules
        else:
            stylesheet_dies = base_stylesheet_dies(False) + color_rules + hiding_rules

        # compute stats
        count_coins = coin_graph_filtered.number_of_nodes() - len(all_hidden_coins_ids)
        count_dies = updated_die_graph.number_of_nodes()
        if view == 'coins':
            components = nx.number_connected_components(coin_graph_filtered) if count_coins else 0
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

        return stylesheet_coins, stylesheet_dies, stats_children, nx_to_elements(updated_die_graph), hidden_out


    @app.callback(
        Output('cy-coins', 'layout'),
        Output('cy-dies', 'layout'),
        Input('layout-selector', 'value'),
        State('graph-view-selector', 'value'),
        State('auto-layout-toggle', 'value'),
        prevent_initial_call=True
    )
    def set_layout(selected_layout, active_view, auto_layout_toggle):
        """
        Set the layout of the coin and die cytoscape instances.

        Parameters
        ----------
        selected_layout : str
            String contains requested layout from layout-selector ui component.
        active_view : str
            Currently selected view from the graph view selector.
        auto_layout_toggle : list
            List contains 'on' if checklist is clicked, else empty.

        Returns
        -------
        dict 
            Layout configuration for the coin cytoscape instance
        dict
            Layout configuration for the die cytoscape instance.
        """

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