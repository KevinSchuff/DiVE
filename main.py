"""
This is the main module, from which you can also start the application. It contains the layout of the page and stores.
"""

import dash
from dash import dcc, html
import dash_cytoscape as cyto

from image_utils import register_merge_route
from proxy import register_image_proxy
from create_view_callbacks import register_create_view_callbacks
from update_view_callbacks import register_update_view_callbacks
from ui_elements_callbacks import register_ui_elements_callbacks


cyto.load_extra_layouts()

app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Get the Flask server instance
server = app.server
register_merge_route(server)
register_image_proxy(server)

app.title = "DiVE"

app.layout = html.Div([
    dcc.Store(id='graph-store-coins'),
    dcc.Store(id='graph-store-dies'),
    dcc.Store(id='filter-values-store', data={}),
    dcc.Store(id='custom-colors-store', data=[]),
    dcc.Store(id='layout-choices', data={'coins': 'dagre', 'dies': 'dagre'}),
    dcc.Store(id='pending-csv', data=None),
    dcc.Store(id='csv-approved', data=None),
    dcc.Store(id="hidden-store", data={"coins": [], "dies": []}), # stores list of coin ids(str), list of dies(obj with id and typ)
    dcc.Store(id="upload-signal", data=0),
    dcc.Upload(id="upload-data", style={"display": "none"}),

    
    # starting overlay
    html.Div(
        id='start-app-overlay',
        className='overlay-backdrop',
        children=html.Div(
            className='overlay-card',
            style={'textAlign': 'center'},
            children=[
                html.Button(
                    "X", id='start-app-overlay-close-btn', n_clicks=0,
                    className='btn-close'
                    ),
                html.H1("Welcome to DiVE"),
                html.H3("DieLink Visualization Environment"),
                html.H4("DiVE transforms labeled coin lists into interactive visualizations."),
                html.Img(src="/assets/dive-pic.png", style={"width": "400px"}),
                html.P(["*Coin pictures from ", html.A("https://www.corpus-nummorum.eu/", href="https://www.corpus-nummorum.eu/", target="_blank"),"."],
                    style={"fontSize": "12px"}),

                html.Div(
                    style={'textAlign': 'left'},
                    children=[
                        html.P(
                            [
                                "DiVE accepts a labeled list of coins as a .csv file.",
                                html.Br(),
                                "Each row represents one coin with die assignments and optional image URLs",
                                html.Br(),
                                "Rename or enter the relevant column names below.",
                                html.Br(),
                                "Then select the .csv file.",
                            ]
                        ),

                        # User Inputs for Column names
                        html.Div([
                            html.Div([
                                html.Label("front die column:"),
                                dcc.Input(
                                    id='front-column',
                                    type='text',
                                    placeholder='Rename related column name to "front die" or enter it here.',
                                    debounce=True,
                                    style={'width': '100%'}
                                ),
                            ], style={'marginBottom': '10px'}),
                            html.Div([
                                html.Label("back die column:"),
                                dcc.Input(
                                    id='back-column',
                                    type='text',
                                    placeholder='Rename related column name to "back die" or enter it here.',
                                    debounce=True,
                                    style={'width': '100%'}
                                ),
                            ], style={'marginBottom': '10px'}),
                            html.Div([
                                html.Label("front image column:"),
                                dcc.Input(
                                    id='front-url-column',
                                    type='text',
                                    placeholder='Rename related column name to "front img" or enter it here.',
                                    debounce=True,
                                    style={'width': '100%'}
                                ),
                            ], style={'marginBottom': '10px'}),
                            html.Div([
                                html.Label("back image column:"),
                                dcc.Input(
                                    id='back-url-column',
                                    type='text',
                                    placeholder='Rename related column name to "back img" or enter it here.',
                                    debounce=True,
                                    style={'width': '100%'}
                                ),
                            ], style={'marginBottom': '10px'}),
                        ], style={'marginTop': '10px'}),
                    ],
                ),

                html.Div(
                    id="upload-container",
                    style={"textAlign": "center"},
                    children=html.Div(
                        [
                            dcc.Upload(
                                id="upload-data",
                                children=html.Button("Choose CSV", style={'margin': '10px'}),
                                multiple=False,
                            ),
                            html.Button("🚀 Test DiVE", id="test-dive-button", n_clicks=0, style={'margin': '10px'}),
                        ],
                        style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center'}
                    ),
                ),

            ]
        ),
    ),

    html.Div(
        id="about-overlay",
        style={"display": "none"},
        className="overlay-backdrop",
        children=html.Div(
            [
                html.Div(
                [
                    html.H3("About DiVE", style={"margin": 0}),
                    html.Button("X", id="about-close-btn", n_clicks=0, className="btn-close", style={"marginLeft": "auto"}),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "16px",},
            ),
                html.Div("Version: 1.0"),
                html.Div("Author: Kevin Schuff"),
                html.Div("Latest version and test.csv file on GitHub."),
                html.A("Open GitHub", href="https://github.com/KevinSchuff/DiVE", target="_blank")
            ],
            className="overlay-card",
            style={'width': '320px'},
        )
    ),


    # Lightbox for coin pictures
    html.Div(
        id='lightbox',
        className='overlay-backdrop',
        style={'display': 'none'},
        children=html.Div([
            html.Button(
                "X", id='lightbox-close', n_clicks=0,
                className='btn-close'
            ),
            html.Div(id='lightbox-body', style={'position':'relative', 'display':'flex',
                                            'flexDirection':'column', 'alignItems':'center'})
        ])
    ),

    
    # Topbar
    html.Div(
        [
            # new csv button
            html.Div(
                [
                    html.Button("Upload new CSV", id="upload-new-csv", n_clicks=0)
                ], style={"flex":"0 0 auto"},
            ),
            # Graph View-Selector
            html.Div([
                dcc.RadioItems(
                    id='graph-view-selector',
                    options=[
                        {'label': html.Strong('Coin-View'), 'value': 'coins'},
                        {'label': html.Strong('Die-View'), 'value': 'dies'}
                    ],
                    value='coins',
                    inline=True
                ),
            ], className="topbar-center"),
                        # new csv button
            html.Div(
                [
                    html.Button("About", id="about-btn", n_clicks=0)
                ], style={"flex":"0 0 auto"},
            ),
        ],
        className="topbar"
    ),
    html.Div(className="divider"),

    # Sidebar and Visualizations
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
                    {'label': 'dagre', 'value': 'dagre'},
                    {'label': 'klay', 'value': 'klay'},
                    {'label': 'grid', 'value': 'grid'},
                    {'label': 'circle', 'value': 'circle'},
                    {'label': 'concentric', 'value': 'concentric'},
                ],
                value='dagre',
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
            html.Div(className="divider"),

            # Edge controls
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
            
            # Coloring Nodes
            html.Div(
                id='color-nodes-container',
                children=[
                    html.Div(className="divider"),
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
                            placeholder='Enter color name or #hexcode',
                            debounce=True,
                            style={'flex': '1', 'marginRight': '4px'}
                        ),
                        html.Button('+', id='add-color-button', n_clicks=0),
                    ], style={'display': 'flex', 'width': '100%', 'marginBottom': '15px'}),
                    html.Div(id='custom-color-dropdowns'),
                ],
            ),

            # Hiding Nodes
            html.Div(
                id='hiding-nodes-container',
                children=[
                    html.Div(className="divider"),
                    html.H3("Hide Nodes"),
                    html.Div(html.Label("by selection:", style={'fontWeight': 'bold'})),
                    html.Div(html.Label("use box selection: shift + left-click + drag"), style={'marginBottom': '4px'}),
                    html.Div(
                        [
                            html.Button("Hide Selection", id='hide-selection-button', title='hides all selected nodes', n_clicks=0),
                            html.Button("Show only Selection", id='show-only-selection-button', title='hides all nodes not in selection', n_clicks=0),
                            html.Button("Reset Selection", id="reset-selection-button", title='resets selection based hiding', n_clicks=0, disabled=True),
                        ],
                        style={
                            'display': 'flex',
                            'justifyContent': 'center',
                            'gap': '12px',
                        }
                    ),
                    html.Div(html.Label("by attribute value:", style={'fontWeight': 'bold'}), style={'marginTop': '20px', 'marginBottom': '10px'}),
                    html.Div(id='filter-dropdowns'),
                ],
            ),

            # Node Details
            html.Div(className="divider"),
            html.H3("Node details"),
            html.Div(id='node-info-box', style={
                'padding': '10px',
                'border': '1px solid #ccc',
                'borderRadius': '8px',
                'maxHeight': '200px',
                'overflowY': 'auto',
                'backgroundColor': '#fbfcfd'
            }),

            # Statistics
            html.Div(className="divider"),
            html.H3("Statistics"),
            html.Div(
                id='stats-box',
                style={
                    'padding': '10px',
                    'border': '1px solid #e2e6ea',
                    'borderRadius': '8px',
                    'maxHeight': '160px',
                    'overflowY': 'auto',
                    'backgroundColor': '#fbfcfd',
                    'marginTop': '6px'
                }
            ),

            # Export
            html.Div(
                id='export-container',
                children=[
                    html.Div(className="divider"),
                    html.H3("Export"),
                    html.Button("Export as PNG", id='export-png-button', n_clicks=0),
                ],
            ),

            ], className="sidebar"),


        # Visualizations
        html.Div([
            # Two Cytoscape instances kept mounted; we toggle visibility only
            cyto.Cytoscape(
            id='cy-coins',
            layout={'name': 'dagre'},
            autoRefreshLayout = False,  # disables applying layout on elements change
            style={'width': '100%', 'height': '100%', 'display': 'block'},
            elements=[],
            stylesheet=[{'selector': 'node', 'style': {'label': 'data(label)', 'width': 200, 'height': 200, 'border-width': 2}}],
            boxSelectionEnabled = True,
            wheelSensitivity=0.1,
            ),
            cyto.Cytoscape(
            id='cy-dies',
            layout={'name': 'dagre'},
            autoRefreshLayout = False,
            style={'width': '100%', 'height': '100%', 'display': 'none'},
            elements=[],
            stylesheet=[{'selector': 'node', 'style': {'label': 'data(label)', 'width': 200, 'height': 200, 'border-width': 2}}],
            boxSelectionEnabled = True,
            wheelSensitivity=0.1,
            ),
        ], className="cyto-views")
    ], style={'display': 'flex', 'flexDirection': 'row', 'height': '87vh'}),

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
], className="app-shell")

register_create_view_callbacks(app)
register_update_view_callbacks(app)
register_ui_elements_callbacks(app)



if __name__ == '__main__':
    app.run(debug=True)
