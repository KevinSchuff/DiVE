"""
This module handles all callbacks that are relevant the UI elements, except the cytoscape instances.
"""

from dash import Input, Output, State, ctx, no_update, dcc, html
import networkx as nx
from uuid import uuid4


def register_ui_elements_callbacks(app):
    """
    Register all dash callbacks relevant to ui elements, except cytoscape instances.

    Parameters
    ----------
    app : dash.Dash
        Dash application instance to which the callbacks will be attached.
    """

    @app.callback(
        Output('layout-choices', 'data'),
        Input('layout-selector', 'value'),
        State('graph-view-selector', 'value'),
        State('layout-choices', 'data'),
    )
    def remember_layout_choice(selected, active_view, choices):
        """
        Remember the layout choices for views.

        Parameters
        ----------
        selected : str
            Requested layout from layout-selector ui component.
        active_view : str
            Currently selected view from the graph view selector.
        choices : dict
            Mapping of view name to layout.

        Returns
        -------
        dict
            Updated Mapping of view name to layout.
        """

        choices = choices or {}
        choices[active_view] = selected
        return choices


    @app.callback(
        Output('layout-selector', 'value'),
        Input('graph-view-selector', 'value'),
        State('layout-choices', 'data'),
    )
    def sync_dropdown_to_view(active_view, choices):
        """
        Synchronize layout dropdown value when switching graph views.

        Parameters
        ----------
        active_view : str
            Currently selected view from the graph view selector.
        choices : dict
            Mapping of view name to layout.

        Returns
        -------
        str
            Current layout from layout-selector ui component.
        """
        
        choices = choices or {}
        return choices.get(active_view, 'dagre')


    @app.callback(
        Output('custom-colors-store', 'data'),
        Input('add-color-button', 'n_clicks'),
        State('new-color-input', 'value'),
        State('custom-colors-store', 'data'),
        prevent_initial_call=True
    )
    def add_custom_color(n_clicks, color_input, color_list):
        """
        Add a new custom color to the color store.

        Parameters
        ----------
        n_clicks : int or None
            Number of times the "add color" button has been clicked.
        color_input : str or None
            The color name or identifier entered by the user.
        color_list : list of str or None
            Current list of custom colors stored in custom-colors-store.

        Returns
        -------
        list of str
            Updated list of custom colors.
        """

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
        """
        Render dropdowns for every custom color.

        Parameters
        ----------
        colors : list of str or None
            List of custom colors stored in custom-colors-store.
        coins_data : dict or None
            Stores graph, node and edge attributes from coins.
        dies_data : dict or None
            Stores graph, node and edge attributes from dies.
        view : str
            Currently selected view from the graph view selector.

        Returns
        -------
        list of dash.html.Div
            A list of containers, each holding a label and a dropdown for a custom color.
        """
        # no custom colors chosen
        if not colors:
            return []
        # use graph data of currently active view
        graph_data = coins_data if view == 'coins' else dies_data
        if not graph_data:
            return []
        # reconstruct NetworkX graph from stored graph data
        G = nx.readwrite.json_graph.node_link_graph(graph_data)
        # collect all attribute:value combinations from nodes
        combinations = set()
        for _, data in G.nodes(data=True):
            for k, v in data.items():
                if v is not None:
                    combinations.add(f"{k}={v}")
        options = [{'label': c, 'value': c} for c in sorted(combinations)]
        # create one dropdown for every custom color
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
        Output('lightbox', 'style'),
        Output('lightbox-body', 'children'),
        Input('cy-coins', 'tapNodeData'),
        Input('cy-dies', 'tapNodeData'),
        Input('lightbox-close', 'n_clicks'),
        State('edge-mode', 'value'),
        prevent_initial_call=True
    )
    def lightbox(coin_data, die_data, close_clicks, edge_mode):
        """
        Show or hide overlay with image, when nodes are clicked.

        Parameters
        ----------
        coin_data : dict or None
            Node data for the tapped coin node from coin cytoscape instance.
        die_data : dict or None
            Node data for the tapped die node from die cytoscape instance.
        close_clicks : int or None
            Number of clicks on the lightbox close button.
        edge_mode : str
            String contains currently selected edge mode for coin-view. Is either front, back or both.

        Returns
        -------
        dict
            Style dictionary for the lightbox container.
        list of dash components
            html.img's components to render inside lightbox body
        """

        trigger = ctx.triggered_id
        url = None
        base_style={
        'position': 'fixed', 'inset': 0,
        'background': 'rgba(0,0,0,0.6)',
        'zIndex': 9999, 'justifyContent': 'center', 'alignItems': 'center',
        'padding': '24px', 'display': 'none'
        }

        # Close button clicked -> hide overlay
        if trigger == 'lightbox-close':
            return {'display': 'none'}, []

        # set data based on what instance triggered callback
        data = coin_data if trigger == 'cy-coins' else die_data
        if not data:
            return {'display': 'none'}, []

        # case 1: die nodes always use this
        if 'bg_die' in data:
            url = data.get('bg_die')
        # case 2: for coin nodes and edge mode is front or back
        elif edge_mode == 'front' or edge_mode == 'back':
            url = data.get(f'bg_{edge_mode}')        
        
        else:  # case 3: for coin nodes and edge mode is both
            front_url= data.get('bg_front')
            back_url = data.get('bg_back')
            # show both pictures if available
            if front_url and back_url:
                children = html.Div(
                    [
                        html.Img(
                            src=front_url,
                            style={'maxWidth': '45vw', 'maxHeight': '90vh', 'objectFit': 'contain'},
                            key=str(uuid4())
                        ) if front_url else html.Div(),
                        html.Img(
                            src=back_url,
                            style={'maxWidth': '45vw', 'maxHeight': '90vh', 'objectFit': 'contain'},
                            key=str(uuid4())
                        ) if back_url else html.Div(),
                    ],
                )
                style = dict(base_style, display='flex')
                return style, [children]
            # fallback if only one or no image exists
            elif front_url:
                url = front_url
            elif back_url:
                url = back_url
            else:
                return {'display': 'none'}, []
            
        # only one picture to display
        if not url:
            return {'display': 'none'}, []
        img = html.Img(
            src=url,
            style={'maxWidth': '90vw', 'maxHeight': '90vh', 'objectFit': 'contain'},
            key=str(uuid4())
        )
        style = dict(base_style, display='flex')
        return style, [img]


    @app.callback(
        Output('node-info-box', 'children'),
        Input('cy-coins', 'mouseoverNodeData'),
        Input('cy-dies', 'mouseoverNodeData')
    )
    def display_node_data(data_coin, data_die):
        """
        Update node-info-box when hovering over nodes.

        Parameters
        ----------
        data_coin : dict or None
            Node data for hovered over node in coin view.
        data_die : dict or None
            Node data for hovered over node in die view.

        Returns
        -------
        dash.html.Div or str
            A component showing the node label and a list of attributes or user instructions.
        """

        # Use whichever view triggered callback
        trig = ctx.triggered_id
        if trig == 'cy-dies':
            data = data_die
        elif trig == 'cy-coins':
            data = data_coin
        else:
            data = data_die or data_coin

        if not data:
            return "Hover over a node to see details"

        label = data.get('label', 'untitled')
        # only show attributes in the csv
        skip_keys = {'id', 'label', 'bg_front', 'bg_back', 'bg_split', 'timeStamp', 'bg_die', 'coin_ids_string'}
        # build list of node attributes
        items = []
        for k, v in data.items():
            if k in skip_keys:
                continue
            items.append(html.Li([html.Strong(f"{k}: "), str(v)]))
        # display node label + list of node attributes
        return html.Div([
            html.H4(f"Node: {label}"),
            html.Ul(items, style={'margin': 0, 'paddingLeft': '18px'})
        ])


    @app.callback(
        Output("reset-selection-button", "disabled"),
        Input("hidden-store", "data"),
    )
    def toggle_reset_selection_button(hidden_store):
        """
        Enable or disable the reset-selection button.

        Parameters
        ----------
        hidden_store : dict or None
            Stored hidden coin and die information.

        Returns
        -------
        bool
            True if reset-selection button should be disabled, else False.
        """
                
        # no store -> keep disabled
        if not hidden_store or not isinstance(hidden_store, dict):
            return True

        # check if hidden store is empty
        coins = hidden_store.get("coins", [])
        dies = hidden_store.get("dies", [])
        if bool(coins) or bool(dies):
            return False
        else:
            return True


    @app.callback(
        Output('cy-coins', 'generateImage'),
        Output('cy-dies', 'generateImage'),
        Input('export-png-button', 'n_clicks'),
        State('graph-view-selector', 'value'),
        prevent_initial_call=True
    )
    def export_png(n_clicks, view):
        """
        Triggers PNG export of the current view.

        Parameters
        ----------
        n_clicks : int or None
            Number of clicks on the export button.
        view : str
            Currently selected view from the graph view selector.

        Returns
        -------
        dict or dash.no_update
            A generateImage configuration dict for coin cytoscape instance if the coin view is active.
        dict or dash.no_update
            A generateImage configuration dict for die cytoscape instance if the die view is active.
        """

        if view == 'dies':
            return no_update, {
                'type': 'png',
                'action': 'download',
                'filename': 'diesgraph_view',
                'options': {          
                'full': False,
                'scale': 4,
                'bg': 'white',
            }
            }
        else:
            return {
                'type': 'png',
                'action': 'download',
                'filename': 'coingraph_view',
                'options': {          
                'full': False,
                'scale': 4,
                'bg': 'white',
            }
            }, no_update


    @app.callback(
        Output('cy-coins', 'autoRefreshLayout'),
        Output('cy-dies', 'autoRefreshLayout'),
        Input('auto-layout-toggle', 'value'),
        prevent_initial_call=False
    )
    def set_auto_layout(toggle_value):
        """
        Toggle automatic layout refresh for both views on element change.

        Parameters
        ----------
        toggle_value : list of str
            List contains 'on' if checklist is clicked, else empty.

        Returns
        -------
        bool
            True if auto-layout is enabled for coin-view, else False.
        bool
            True if auto-layout is enabled for die-view, else False
        """
        enable_auto_layout = 'on' in (toggle_value or [])
        return enable_auto_layout, enable_auto_layout


    @app.callback(
        Output('start-app-overlay', 'style'),
        Input('upload-data', 'contents'),
        prevent_initial_call=False
    )
    def close_start_app_overlay(upload_data):
        """
        Hide the start-app overlay after data upload.

        Parameters
        ----------
        upload_data : str or None
            base64 encoded string containing uploaded CSV file's content

        Returns
        -------
        dict or dash.no_update
            CSS Style dict for start-app-overlay.
        """

        if upload_data is not None:
            return {'display': 'none'}
        else:
            return no_update