"""
This module is responsible for creating the first visualizations based on the chosen csv file. It also populates the dropdowns of ui elements.
"""

from dash import Input, Output, State, ctx, no_update, dcc, html
import networkx as nx
import base64, csv, io

from csv_handler import load_graph_from_csv, normalize_key
from graph_handler import add_edges_by_mode, create_dies_graph, nx_to_elements, enrich_images


def register_create_view_callbacks(app):
    """
    This function registers all relevant callbacks to creating the first visualizations.
    """
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
        This callback gatekeeps larger csv files. if it is < 100 rows accept immediately, else stash in pending-csv and show dialogue box.

        Parameters
        ----------
        contents : str or None
            base64 encoded string containing uploaded CSV file's content
        ok_clicks : int or None
            Number of times the OK button in dialogue box was clicked.
        cancel_clicks : int or None
            Number of times the Cancel button in dialogue box was clicked.
        pending : str or None
            Temporary store for base64 encoded string containing uploaded CSV file's content when file too big.

        Returns
        -------
        csv_approved_data : str or None
            Approved base64 encoded string containing uploaded CSV file's content, which may be limited.
        pending_csv_data : str or None
            CSV data to store temporarily while awaiting user confirmation.
        csv_size_warning_displayed : bool  
            Decides to display or hide the dialogue box.
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
        Output('cy-coins', 'elements'),
        Output('cy-dies', 'elements'),
        Output('filter-dropdowns', 'children'),
        Output({'type': 'color-dropdown', 'index': 'red'}, 'options'),
        Output({'type': 'color-dropdown', 'index': 'blue'}, 'options'),
        Output({'type': 'color-dropdown', 'index': 'green'}, 'options'),
        Output({'type': 'color-dropdown', 'index': 'red'}, 'value'),
        Output({'type': 'color-dropdown', 'index': 'blue'}, 'value'),
        Output({'type': 'color-dropdown', 'index': 'green'}, 'value'),
        Input('csv-approved', 'data'),
        State('front-column', 'value'),
        State('back-column', 'value'),
        State('front-url-column', 'value'),
        State('back-url-column', 'value'),
        State('edge-mode', 'value'),
    )
    def handle_file_upload(contents, front_column, back_column, front_url_column, back_url_column, edge_mode):
        """
        Decodes CSV and builds coin graph and die graph. prepares filter und color options UI

        Parameters
        ----------
        contents : str or None
            Base64 encoded string containing uploaded CSV file's content
        front_column : str or None
            Text in 'front-column' input fields.
        back_column : str or None
            Text in 'front-column' input fields.
        front_url_column : str or None
            Text in 'front-url-column' input fields.
        back_url_column : str or None
            Text in 'back-url-column' input fields.
        edge_mode : 'front' or 'back' or 'both' or None
            Selected option from radio buttons for edge mode

        Returns
        -------
        dict
            Stores graph, node and edge attributes from coins.
        dict
            Stores graph, node and edge attributes from dies.
        list of dict  
            Element list of dash cytoscape instance cy-coins.
        list of dict 
            Element list of dash cytoscape instance cy-dies.
        list of dash.html.Div
            Contains one div per coin attribute, each with label and dropdown(all possible values).
        list of dict 
            Contains dropdown options with all possible attribute:value combinations for red coloring.
        list of dict  
            Contains dropdown options with all possible attribute:value combinations for blue coloring.
        list of dict  
            Contains dropdown options with all possible attribute:value combinations for green coloring.
        list of dict 
            Contains dropdown selection for red coloring.
        list of dict  
            Contains dropdown selection for blue coloring.
        list of dict  
            Contains dropdown selection for green coloring.
        """

        if not contents:
            return (no_update, no_update, no_update, no_update, [], [], [], [], None, None, None)
        
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        coins_graph = load_graph_from_csv(decoded)

        # Normalize the user-provided (or default) column names
        front_key = normalize_key(front_column or "front die")
        back_key = normalize_key(back_column or "back die")
        front_url_key = normalize_key(front_url_column or "front img")
        back_url_key = normalize_key(back_url_column or "back img")

        # build edges according to selected mode
        add_edges_by_mode(coins_graph, front_key, back_key, edge_mode)

        # maps each attribute to all its values like {attribute -> set(values)} for filter dropdown
        attribute_values = dict()
        # set of  all "attribute=value" strings for color dropdown
        combinations = set()
        for _, data in coins_graph.nodes(data=True):
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
                    placeholder=f"Search {attr} value"
                )
            ])
            for attr, vals in attribute_values.items()
        ]
        # build options for color dropdowns, expects [{'label':displayed text, 'value':returned value}]
        options = [{'label': c, 'value': c} for c in sorted(combinations)]

        # build die-graph with input columns
        dies_graph, _ = create_dies_graph(
            coins_graph, front_col=front_key, back_col=back_key, hidden_coins=[], hidden_dies=[],
            front_url_col=front_url_key, back_url_col=back_url_key
            )

        # cytoscape elements for graphs
        coins_base_elements = nx_to_elements(coins_graph)             # base (no images)
        dies_elements = nx_to_elements(dies_graph)

        coins_with_images_elements = enrich_images(coins_graph, coins_base_elements, front_url_key, back_url_key)

        return (
            nx.readwrite.json_graph.node_link_data(coins_graph),
            nx.readwrite.json_graph.node_link_data(dies_graph),
            coins_with_images_elements,
            dies_elements,
            filter_ui,
            options,
            options,
            options,
            None,
            None,
            None
        )

