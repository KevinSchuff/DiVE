from proxy import register_image_proxy, proxify
import dash
from dash import dcc, html, Input, Output, State, ctx, no_update, ALL
import dash_cytoscape as cyto
import networkx as nx
import base64
import re
from CSVHandler import load_graph_from_csv, normalize_key
import io
import zipfile
import csv
import mimetypes
from flask import Response, abort 
from urllib.parse import quote, urlencode
from image_utils import bg_url_from_csv_value, register_merge_route
import time
from callbacks import register_callbacks

cyto.load_extra_layouts()

app = dash.Dash(__name__)
# Get the Flask server instance and register the proxy
server = app.server
register_merge_route(server)
register_image_proxy(server)

app.title = "Network visualization"

# In-memory store for images from the ZIP
#ZIP_IMAGE_STORE = {}



"""
# Flask route to serve images from the ZIP
@server.route("/zipimg/<path:filename>")
def serve_zip_image(filename):
    key = norm_path(filename)
    if key not in ZIP_IMAGE_STORE:
        abort(404)
    data = ZIP_IMAGE_STORE[key]
    mime = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return Response(data, mimetype=mime)
"""

app.layout = html.Div([
    dcc.Store(id='graph-store-coins'),
    dcc.Store(id='graph-store-dies'),
    dcc.Store(id='elements-coins'),
    dcc.Store(id='elements-dies'),
    dcc.Store(id='filter-values-store', data={}),
    dcc.Store(id='custom-colors-store', data=[]),
    dcc.Store(id='zip-file-list', data=[]),
    dcc.Store(id='layout-choices', data={'coins': 'grid', 'dies': 'grid'}),
    dcc.Store(id='pending-csv', data=None),
    dcc.Store(id='csv-approved', data=None),
    dcc.Store(id='elements-coins-base'),   # base elements (no bg_* fields)
    dcc.Store(id='dies-force-grid-once', data=True),
    dcc.Store(id="hidden-store", data={"coins": [], "dies": []}), # stores list of coin ids(str), list of dies(obj with id and typ)
    dcc.Store(id="layout-trigger"),




    # User Inputs for Column names
    html.Div([
        html.Label("Front column:"),
        dcc.Input(
            id='front-column',
            type='text',
            placeholder='Stempeluntergruppe Av',
            debounce=True,
            style={'marginRight': '10px'}
        ),
        html.Label("Back column:"),
        dcc.Input(
            id='back-column',
            type='text',
            placeholder='Stempeluntergruppe Rv',
            debounce=True,
            style={'marginRight': '10px'}
        ),
        html.Label("Front img:"),
        dcc.Input(
            id='front-column-url',
            type='text',
            placeholder='Vorderseite Bild',
            debounce=True,
            style={'marginRight': '10px'}
        ),
        html.Label("Back img:"),
        dcc.Input(
            id='back-column-url',
            type='text',
            placeholder='Rückseite Bild',
            debounce=True
        ),
], style={'margin': '10px 0'}),





    # Upload CSV/ZIP, export buttons
    html.Div([
    dcc.Upload(
        id='upload-data',
        children=html.Button("Choose CSV", style={'margin': '10px'}),
        multiple=False
    ),
    # out of comission
    dcc.Upload(
        id='upload-zip',
        children=html.Button("Choose ZIP", style={'margin': '10px'}),
        multiple=False
    ),
    html.Div(id='zip-status', style={'marginLeft': '10px'}),

    html.Button("Export as PNG", id='export-png-button', n_clicks=0, style={'margin': '10px'}),
    html.Button("Hide Selection", id='hide-selection-button', n_clicks=0, style={'margin': '10px'}),
    html.Button("Show only Selection", id='show-only-selection-button', n_clicks=0, style={'margin': '10px'}),
    html.Button("Reset Selection", id="reset-selection-button", n_clicks=0, disabled=True, style={'margin': '10px'}),
], style={'display': 'flex', 'alignItems': 'center'}),
    html.Hr(),


    # Graph View-Selector
    html.Div([
    html.Label("Select View:", style={'marginRight': '10px'}),
    dcc.RadioItems(
        id='graph-view-selector',
        options=[
            {'label': 'Coin-View', 'value': 'coins'},
            {'label': 'Die-View', 'value': 'dies'}
        ],
        value='coins',
        inline=True
    ),
], style={'display': 'flex', 'alignItems': 'center'}),


    # Lightbox for coin pictures
    html.Div(
        id='lightbox',
        style={
            'display': 'none',                      # hidden by default
            'position': 'fixed', 'inset': 0,
            'background': 'rgba(0,0,0,0.6)',
            'zIndex': 9999,
            'justifyContent': 'center', 'alignItems': 'center',
            'padding': '24px',
        },
        children=html.Div([
            html.Button(
                "✕", id='lightbox-close', n_clicks=0,
                style={'position': 'absolute', 'top': '20px', 'right': '20px', 'fontSize': '20px'}
            ),
            html.Img(
                id='lightbox-img',
                style={'maxWidth': '90vw', 'maxHeight': '90vh'}
            ),
        ], style={'position': 'relative', 'display': 'flex', 'flexDirection': 'column', 'alignItems': 'center'})
    ),


    # Sidebar and Graph
    html.Div([
        # Sidebar
        html.Div([ 
            # Layout           
            html.H3("Layout"),
            html.Label("Layout-Type"),
            dcc.Dropdown(
                id='layout-selector',
                options=[
                    {'label': 'cose', 'value': 'cose'},
                    {'label': 'cose-bilkent', 'value': 'cose-bilkent'},
                    {'label': 'cola (experimental)', 'value': 'cola'},
                    {'label': 'dagre', 'value': 'dagre'},
                    {'label': 'klay', 'value': 'klay'},
                    {'label': 'grid', 'value': 'grid'},
                    {'label': 'circle', 'value': 'circle'},
                    {'label': 'concentric', 'value': 'concentric'},
                ],
                value='grid',
                clearable=False,
                style={'marginBottom': '10px'}
            ),
            dcc.Checklist(
                id='auto-layout-toggle',
                options=[{'label': 'Auto layout', 'value': 'on'}],
                value=['on'],
                inline=True,
                style={'marginBottom': '10px'}
            ),
            html.Hr(),

            html.Div([
                html.H3("Edge options"),
                html.Div(
                    id='scale-weighted-edges-container',
                    children=[
                        dcc.Checklist(
                            id='scale-weighted-edges',
                            options=[{'label': 'scale edges with weight', 'value': 'on'}],
                            value=['on'],
                            inline=True,
                            style={'marginBottom': '10px'}
                        ),
                    ],
                ),
                html.Div(
                    id='edge-mode-container',
                    children=[
                        html.Div([
                            html.Label("Edge condition:", style={'marginRight': '10px'}),
                            dcc.RadioItems(
                                id='edge-mode',
                                options=[
                                    {'label': 'Front', 'value': 'front'},
                                    {'label': 'Back', 'value': 'back'},
                                    {'label': 'Front + Back', 'value': 'both'}
                                ],
                                value='front',
                                inline=True
                            )
                        ], style={'display': 'flex', 'alignItems': 'center'}),
                    ]
                ),
            ]),
            
            html.Div(
                id='color-nodes-container',
                children=[
                    html.Hr(),
                    # Color Nodes
                    html.H3("Color nodes by attribute value"),
                    html.Label("Red:"),
                    dcc.Dropdown(id={'type': 'color-dropdown', 'index': 'red'}, multi=True, searchable=True),
                    html.Label("Blue:"),
                    dcc.Dropdown(id={'type': 'color-dropdown', 'index': 'blue'}, multi=True, searchable=True),
                    html.Label("Green:"),
                    dcc.Dropdown(id={'type': 'color-dropdown', 'index': 'green'}, multi=True, searchable=True),
                    html.H4("Add custom colors"),
                    html.Div([
                        dcc.Input(
                            id='new-color-input',
                            type='text',
                            placeholder='Color name or #hexcode',
                            debounce=True,
                            style={'width': '70%', 'marginRight': '10px'}
                        ),
                        html.Button('+', id='add-color-button', n_clicks=0),
                    ], style={'marginBottom': '15px'}),
                    html.Div(id='custom-color-dropdowns'),
                ],
            ),

            html.Hr(),
            html.H3("Hide Nodes"),
            html.Div(id='filter-dropdowns'),

            html.Hr(),
            html.H3("Node details"),
            html.Div(id='node-info-box', style={
                'padding': '10px',
                'border': '1px solid #ccc',
                'maxHeight': '200px',
                'overflowY': 'auto',
                'backgroundColor': '#f9f9f9'
            }),
            html.Hr(),
            html.H3("Statistics"),
            html.Div(
                id='stats-box',
                style={
                    'padding': '10px',
                    'border': '1px solid #ccc',
                    'maxHeight': '160px',
                    'overflowY': 'auto',
                    'backgroundColor': '#f9f9f9',
                    'marginTop': '6px'
                }
            ),
            ], style={'flex': '1', 'padding': '10px', 'maxWidth': '400px', 'overflowY': 'auto'}),

        # Graphs
        html.Div([
            # Two Cytoscape instances kept mounted; we toggle visibility only
            cyto.Cytoscape(
            id='cy-coins',
            layout={'name': 'grid'},
            autoRefreshLayout = False,  # disables applying layout on elements change
            style={'width': '100%', 'height': '800px', 'display': 'block'},
            elements=[],
            stylesheet=[{'selector': 'node', 'style': {'label': 'data(label)', 'width': 200, 'height': 200, 'border-width': 2}}],
            boxSelectionEnabled = True,
            wheelSensitivity=0.1,
            ),
            cyto.Cytoscape(
            id='cy-dies',
            layout={'name': 'grid'},
            autoRefreshLayout = False,
            style={'width': '100%', 'height': '800px', 'display': 'none'},
            elements=[],
            stylesheet=[{'selector': 'node', 'style': {'label': 'data(label)', 'width': 200, 'height': 200, 'border-width': 2}}],
            boxSelectionEnabled = True,
            wheelSensitivity=0.1,
            ),
        ], style={'flex': '3', 'padding': '10px'})
    ], style={'display': 'flex', 'flexDirection': 'row', 'height': '90vh'}),

    # pop up for csv > 100lines
    dcc.ConfirmDialog(
        id='csv-size-warning',
        message=(
            "Your coin list exceeds the recommended length of 100 coins.\n"
            "This may reduce performance.\n\n"
            "Press OK to continue with the full list.\n"
            "Press Cancel to test with a reduced set of 100."
        ),
        displayed=False
    ),
])


register_callbacks(app)





if __name__ == '__main__':
    app.run(debug=True)