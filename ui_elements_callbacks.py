from dash import Input, Output, State, ctx, no_update, ALL, dcc, html
import networkx as nx
from uuid import uuid4


def register_ui_elements_callbacks(app):

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
        Output('lightbox', 'style'),
        Output('lightbox-body', 'children'),
        Input('cy-coins', 'tapNodeData'),
        Input('cy-dies', 'tapNodeData'),
        Input('lightbox-close', 'n_clicks'),
        State('edge-mode', 'value'),
        prevent_initial_call=True
    )
    def lightbox(coin_data, die_data, close_clicks, edge_mode):
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

        # only in die data
        if 'bg_die' in data:
            url = data.get('bg_die')
        
        elif edge_mode == 'front' or edge_mode == 'back':
            url = data.get(f'bg_{edge_mode}')        
        
        else:  # edgemode both
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
            # fallback on front or back image
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
        skip_keys = {'id', 'label', 'bg_front', 'bg_back', 'bg_split', 'timeStamp', 'bg_die', 'coin_ids_string'}
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
        Output("reset-selection-button", "disabled"),
        Input("hidden-store", "data"),
    )
    def toggle_unhide_button(hidden_store):
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
        on = 'on' in (toggle_value or [])
        return on, on


    @app.callback(
        Output('start-app-overlay', 'style'),
        Input('upload-data', 'contents'),
        prevent_initial_call=False
    )
    def close_start_app_overlay(upload_data):
        if upload_data is not None:
            return {'display': 'none'}
        else:
            return no_update