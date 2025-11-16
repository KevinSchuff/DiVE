from dash import Input, Output, State, ctx, no_update, ALL, dcc, html
import networkx as nx
import base64, csv, io
from urllib.parse import urlencode
from CSVHandler import load_graph_from_csv, normalize_key, bg_url_from_csv_value
from graph_handler import add_edges_by_mode, create_dies_graph, nx_to_elements





def register_create_view_callbacks(app):
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

            # if uploaded csv too big, stash csv and show dialogue box
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
        dies_graph, _ = create_dies_graph(
            G, front_col=front_key, back_col=back_key, hidden_coins=[], hidden_dies=[],
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