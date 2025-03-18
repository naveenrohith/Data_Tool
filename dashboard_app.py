import dash
from dash import html, dcc, Input, Output, State, Dash
import dash_bootstrap_components as dbc
import pandas as pd
import io
import base64
import plotly.express as px
import requests
from datetime import datetime, timedelta
import os
from flask_caching import Cache

# Initialize cache
cache = Cache(config={'CACHE_TYPE': 'simple'})  # Simple in-memory cache

# Global dictionaries
uploaded_data_store = {}
weather_data_store = {}

# Constants
MAX_POINTS = 1000
STYLE_NON_EDITABLE = {'userSelect': 'none', 'outline': 'none'}
PROPS_NON_EDITABLE = {'tabIndex': "-1", 'contentEditable': "false"}
BASE_NAV_STYLE = {'flex': 1, 'textAlign': 'center', 'padding': '15px', 'cursor': 'pointer', 
                  'margin': '5px', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}
GRAPH_LAYOUT = dict(template='plotly_white', font=dict(family='Roboto, sans-serif', size=14, color='#333'),
                    title_font=dict(size=18, color='#0056D2'), paper_bgcolor='#ffffff', plot_bgcolor='#f8f9fa',
                    margin=dict(l=50, r=50, t=80, b=50), showlegend=True, 
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5))

def setup_dashboard_app(app: Dash):
    # Attach cache to the Flask server
    cache.init_app(app.server)

    active_style, inactive_style = BASE_NAV_STYLE.copy(), BASE_NAV_STYLE.copy()
    active_style.update({'backgroundColor': '#4fc3f7', 'color': 'white'})
    inactive_style.update({'backgroundColor': '#b3e5fc', 'color': '#333'})

    # Add external stylesheet for Roboto font
    app.index_string = app.index_string.replace(
        '</head>',
        '<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">\n</head>'
    )

    app.layout = dbc.Container([
        html.Div(html.H1('Data Consumption Tool', style={'textAlign': 'center', 'color': '#007BFF', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}), 
                 **PROPS_NON_EDITABLE),
        html.Div([
            html.Div('Dashboard', id='nav-dashboard', className='nav-item', style=inactive_style, **PROPS_NON_EDITABLE),
            html.Div('Data Upload', id='nav-data-upload', className='nav-item', style=active_style, **PROPS_NON_EDITABLE),
            html.Div('Weather', id='nav-weather', className='nav-item', style=inactive_style, **PROPS_NON_EDITABLE),
            html.Div('Settings', id='nav-settings', className='nav-item', style=inactive_style, **PROPS_NON_EDITABLE),
        ], id='nav-bar', style={'display': 'flex', 'border': '1px solid #ddd', 'borderRadius': '8px', 
                                'marginBottom': '30px', 'marginTop': '20px', 'backgroundColor': '#ffffff',
                                'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
        html.Div(id='page-content', style={'minHeight': '500px', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
        dcc.Location(id='url', refresh=True)  # For redirecting on logout
    ], fluid=True, style={'maxWidth': '1400px', 'padding': '30px', 'backgroundColor': '#f8f9fa', **STYLE_NON_EDITABLE})

    @app.callback(Output('page-content', 'children'), 
                  [Input('nav-dashboard', 'n_clicks'), 
                   Input('nav-data-upload', 'n_clicks'),
                   Input('nav-weather', 'n_clicks'),
                   Input('nav-settings', 'n_clicks')])
    def update_page(*clicks):
        return get_page_content(dash.callback_context)

    @app.callback([Output('nav-dashboard', 'style'), 
                   Output('nav-data-upload', 'style'),
                   Output('nav-weather', 'style'),
                   Output('nav-settings', 'style')],
                  [Input('nav-dashboard', 'n_clicks'),
                   Input('nav-data-upload', 'n_clicks'),
                   Input('nav-weather', 'n_clicks'),
                   Input('nav-settings', 'n_clicks')])
    def update_tab_styles(*clicks):
        ctx = dash.callback_context
        active_tab = 'nav-data-upload' if not ctx.triggered else ctx.triggered[0]['prop_id'].split('.')[0]
        styles = [inactive_style.copy(), inactive_style.copy(), inactive_style.copy(), inactive_style.copy()]
        styles[['nav-dashboard', 'nav-data-upload', 'nav-weather', 'nav-settings'].index(active_tab)] = active_style.copy()
        return styles

    @app.callback(Output('upload-output', 'children'), 
                  [Input('upload-data', 'contents'),
                   Input('reset-button', 'n_clicks')], 
                  [State('upload-data', 'filename')])
    def handle_file_upload(contents, reset_clicks, filename):
        ctx = dash.callback_context
        if ctx.triggered_id == 'reset-button':
            uploaded_data_store.clear()
            return html.P('Dataset cleared. Please upload a new file.', 
                          style={'color': '#dc3545', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE)
        return process_file_upload(contents, filename)

    @cache.memoize(timeout=3600)  # Cache for 1 hour
    def fetch_weather_data_from_api(start_date, end_date):
        api_key = os.environ.get('WEATHER_API_KEY', '6K9Z93LW56Z4TWPWWVN5DW2M4')
        location = "Hyderabad, India"
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}/{start_date}/{end_date}?key={api_key}&unitGroup=metric&include=days"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    @app.callback(
        [Output('weather-output', 'children'), 
         Output('weather-data-store', 'data'),
         Output('weather-retry-button', 'style')],
        [Input('weather-date-range', 'start_date'),
         Input('weather-date-range', 'end_date'),
         Input('weather-retry-button', 'n_clicks')],
        prevent_initial_call=False
    )
    def fetch_weather_data(start_date, end_date, retry_clicks):
        current_date = datetime.now().date()  # Get current date (March 15, 2025)
        
        # Set default dates if none provided
        if not start_date or not end_date:
            default_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            default_end = current_date.strftime('%Y-%m-%d')
            start_date, end_date = default_start, default_end
            return (dbc.Alert(f"Using default range: {datetime.strptime(default_start, '%Y-%m-%d').strftime('%d-%m-%Y')} to {datetime.strptime(default_end, '%Y-%m-%d').strftime('%d-%m-%Y')}.", 
                              color="success", style={'fontFamily': 'Roboto, sans-serif'}),
                    None,  # No data yet, let graph handle empty state
                    {'display': 'none'})

        try:
            start_date_api = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_api = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return (dbc.Alert("Invalid date format. Dates should be in YYYY-MM-DD format.", 
                              color="danger", style={'fontFamily': 'Roboto, sans-serif'}),
                    None,
                    {'display': 'inline-block'})

        # Check if dates are in the future
        if start_date_api > current_date or end_date_api > current_date:
            return (dbc.Alert("Future dates are not allowed. Please select dates up to today only.", 
                              color="danger", style={'fontFamily': 'Roboto, sans-serif'}),
                    None,
                    {'display': 'inline-block'})
        
        # Check if end date is before start date
        if end_date_api < start_date_api:
            return (dbc.Alert("End date must be after start date.", 
                              color="danger", style={'fontFamily': 'Roboto, sans-serif'}),
                    None,
                    {'display': 'inline-block'})

        try:
            # Use cached API call
            data = fetch_weather_data_from_api(start_date, end_date)
            df = pd.DataFrame(data['days'])
            df['datetime'] = pd.to_datetime(df['datetime'])
            weather_data_store['data'] = df.to_dict('records')
            print("Weather data fetched:", weather_data_store['data'])  # Debug print
            return (dbc.Alert(f"Weather data fetched for Hyderabad, India from {start_date_api.strftime('%d-%m-%Y')} to {end_date_api.strftime('%d-%m-%Y')}.", 
                              color="success", style={'fontFamily': 'Roboto, sans-serif'}),
                    df.to_dict('records'),
                    {'display': 'none'})
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                error_msg = "Rate limit exceeded, please try again later."
            elif e.response.status_code == 400:
                error_msg = "Invalid date range or location."
            else:
                error_msg = f"Error fetching weather data: {str(e)}"
            return (dbc.Alert(error_msg, color="danger", style={'fontFamily': 'Roboto, sans-serif'}),
                    None,
                    {'display': 'inline-block', 'marginTop': '15px'})
        except Exception as e:
            return (dbc.Alert(f"Error fetching weather data: {str(e)}", color="danger", style={'fontFamily': 'Roboto, sans-serif'}),
                    None,
                    {'display': 'inline-block', 'marginTop': '15px'})

    @app.callback(
        Output('weather-graph', 'figure'),
        [Input('weather-data-store', 'data'),
         Input('weather-metrics', 'value')]
    )
    def update_weather_graph(data, metrics):
        print("Graph data:", data, "Metrics:", metrics)  # Debug print
        if not data or not metrics:
            fig = px.line(title="No data available", template='plotly_white')
            fig.update_layout(**GRAPH_LAYOUT, xaxis_title="Date", yaxis_title="Value")
            fig.add_annotation(text="No data to display. Please fetch weather data.", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            return fig
        
        df = pd.DataFrame(data)
        if df.empty:
            fig = px.line(title="No data available", template='plotly_white')
            fig.update_layout(**GRAPH_LAYOUT, xaxis_title="Date", yaxis_title="Value")
            fig.add_annotation(text="No data to display.", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            return fig

        if len(df) > MAX_POINTS:
            df = df.iloc[::len(df) // MAX_POINTS, :].copy()
        
        # Ensure metrics exist in data
        valid_metrics = [m for m in metrics if m in df.columns]
        if not valid_metrics:
            fig = px.line(title="No valid metrics selected", template='plotly_white')
            fig.update_layout(**GRAPH_LAYOUT, xaxis_title="Date", yaxis_title="Value")
            fig.add_annotation(text="Selected metrics not found in data.", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            return fig

        df_melted = df.melt(id_vars=['datetime'], value_vars=valid_metrics, var_name='Metric', value_name='Value')
        fig = px.line(df_melted, x='datetime', y='Value', color='Metric',
                      title="Weather Data for Hyderabad, India",
                      color_discrete_sequence=['#00A1D6', '#FF6B6B', '#28A745'])
        fig.update_layout(**GRAPH_LAYOUT, xaxis_title="Date", yaxis_title="Value", legend_title_text='')
        return fig

    @app.callback(
        [Output('weather-date-range', 'start_date'),
         Output('weather-date-range', 'end_date')],
        [Input('weather-presets', 'value')]
    )
    def update_date_range(preset):
        current_date = datetime.now().date()  # Ensure end date doesn't exceed current date
        end_date = current_date
        if preset == '7days':
            start_date = end_date - timedelta(days=7)
        elif preset == '30days':
            start_date = end_date - timedelta(days=30)
        elif preset == '1year':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=7)
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

    # Updated callbacks for chiller graphs using a loop
    for graph_id, title, yaxis, input_id in [
        ('chiller-power-graph', 'Chiller Power', 'Power (kW)', 'chiller-power-checklist'),
        ('supply-temp-graph', 'Chiller Water Supply Temperature', 'Temperature (°C)', 'supply-temp-checklist'),
        ('return-temp-graph', 'Chiller Water Return Temperature', 'Temperature (°C)', 'return-temp-checklist')
    ]:
        @app.callback(Output(graph_id, 'figure'), 
                      Input(input_id, 'value'))
        def update_graph(cols):
            df, x_col = prepare_data(cols or [])
            fig = px.line(df, x=x_col, y=cols or [], title=title, color_discrete_sequence=['#00A1D6', '#FF6B6B']) \
                  if df is not None else px.line()
            fig.update_layout(**GRAPH_LAYOUT, xaxis_title=x_col, yaxis_title=yaxis)
            return fig

    @app.callback(
        Output('url', 'pathname'),
        Input('logout-button', 'n_clicks'),
        prevent_initial_call=True
    )
    def handle_logout(n_clicks):
        if n_clicks:
            return '/logout'
        return dash.no_update

def prepare_data(selected_cols):
    if 'data' not in uploaded_data_store or uploaded_data_store['data'].empty:
        return None, None
    df = uploaded_data_store['data']
    if len(df) > MAX_POINTS:
        df = df.iloc[::len(df) // MAX_POINTS, :].copy()
    x_col = 'Date/Time' if 'Date/Time' in df.columns else \
            ('Date/Time' if 'Date' in df.columns and 'Time' in df.columns else df.columns[0])
    if x_col == 'Date/Time':
        df[x_col] = pd.to_datetime(
            df['Date/Time'] if 'Date/Time' in df.columns else df['Date'] + ' ' + df['Time'], 
            format='%m/%d/%Y %H:%M:%S' if 'Date/Time' in df.columns else None, errors='coerce')
    for col in selected_cols:
        df[col] = pd.to_numeric(df.get(col, pd.Series()), errors='coerce')
    return df, x_col

def get_page_content(ctx):
    tab_id = 'nav-data-upload' if not ctx.triggered else ctx.triggered[0]['prop_id'].split('.')[0]
    current_date = datetime.now().date()  # For weather date picker max limit
    
    if tab_id == 'nav-dashboard':
        if 'data' in uploaded_data_store and not uploaded_data_store['data'].empty:
            df = uploaded_data_store['data']
            power_cols = [col for col in df.columns if 'chiller' in col.lower() and 'power' in col.lower()]
            supply_cols = [col for col in df.columns if ('supply' in col.lower() or 'chws' in col.lower()) and ('temp' in col.lower() or 't' in col.lower())]
            return_cols = [col for col in df.columns if ('return' in col.lower() or 'chwr' in col.lower() or 'ret' in col.lower()) and ('temp' in col.lower() or 't' in col.lower())]
            sections = [
                ('Chiller Power', 'chiller-power-checklist', power_cols, 'chiller-power-graph'),
                ('Supply Temperature', 'supply-temp-checklist', supply_cols, 'supply-temp-graph'),
                ('Return Temperature', 'return-temp-checklist', return_cols, 'return-temp-graph')
            ]
            return html.Div([
                html.P(f"Available columns in dataset: {', '.join(df.columns)}", 
                       style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', 'marginTop': '15px', **STYLE_NON_EDITABLE}, 
                       **PROPS_NON_EDITABLE) if not any([power_cols, supply_cols, return_cols]) else None,
                *[dbc.Row(dbc.Col(dbc.Card([
                    dbc.CardHeader(html.H5(title, style={'color': '#0056D2', 'fontWeight': '700', 'textAlign': 'center', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, 
                                          **PROPS_NON_EDITABLE)),
                    dbc.CardBody([
                        dcc.Checklist(id=check_id, options=[{'label': col, 'value': col} for col in cols], 
                                      value=cols, style={'marginBottom': '20px', 'fontFamily': 'Roboto, sans-serif'}),
                        html.P(f"No columns detected for {title}.", style={'color': '#dc3545', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE) if not cols else None,
                        dcc.Graph(id=graph_id, style={'height': '400px'})
                    ])
                ], style={'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'borderRadius': '10px', 'marginBottom': '25px'}))) 
                for title, check_id, cols, graph_id in sections]
            ], style=STYLE_NON_EDITABLE, **PROPS_NON_EDITABLE)
        return html.Div([
            html.H3('Dashboard', style={'color': '#0056D2', 'marginBottom': '25px', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
            html.P('Upload a dataset to view visualizations.', style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE)
        ], style=STYLE_NON_EDITABLE, **PROPS_NON_EDITABLE)

    elif tab_id == 'nav-data-upload':
        return dbc.Card(dbc.CardBody([
            html.P('Upload only .csv files', style={'color': '#dc3545', 'marginBottom': '20px', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
            dcc.Upload(id='upload-data', 
                       children=html.Div(['Drag and Drop or ', html.A('Select Files', style={'color': '#00A1D6', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE)], 
                                        style=STYLE_NON_EDITABLE, **PROPS_NON_EDITABLE),
                       style={'width': '100%', 'height': '100px', 'lineHeight': '100px', 'borderWidth': '2px', 'borderStyle': 'dashed', 
                              'borderRadius': '10px', 'textAlign': 'center', 'backgroundColor': '#f8f9fa', 'borderColor': '#ced4da', 
                              'marginBottom': '25px', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, multiple=False),
            dbc.Button('Reset Dataset', id='reset-button', color='danger', style={'marginRight': '15px', 'borderRadius': '8px'}),
            dcc.Loading(id="loading-upload", children=html.Div(id='upload-output', style={'marginTop': '25px', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, 
                                                               **PROPS_NON_EDITABLE), type="circle", color='#00A1D6')
        ]), style={'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'borderRadius': '10px', 'background': 'linear-gradient(135deg, #ffffff, #f8f9fa)', **STYLE_NON_EDITABLE})

    elif tab_id == 'nav-weather':
        default_start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        default_end_date = current_date.strftime('%Y-%m-%d')
        return dbc.Card(dbc.CardBody([
            html.H2("Weather Data", style={'color': '#0056D2', 'marginBottom': '25px', 'fontFamily': 'Roboto, sans-serif', 'fontWeight': '700', **STYLE_NON_EDITABLE}),
            html.P("Location: Hyderabad, India", style={'color': '#666', 'marginBottom': '20px', 'fontFamily': 'Roboto, sans-serif', 'fontSize': '16px', **STYLE_NON_EDITABLE}),
            dbc.Row([
                dbc.Col([
                    dbc.Label("Select Date Range", style={'color': '#333', 'fontFamily': 'Roboto, sans-serif', 'fontWeight': '500', **STYLE_NON_EDITABLE}),
                    dcc.DatePickerRange(
                        id='weather-date-range',
                        start_date=default_start_date,
                        end_date=default_end_date,
                        max_date_allowed=current_date,
                        display_format='DD-MM-YYYY',
                        style={'marginBottom': '20px', 'fontFamily': 'Roboto, sans-serif'},
                        className='custom-date-picker'
                    )
                ], width=6),
                dbc.Col([
                    dbc.Label("Select Preset", style={'color': '#333', 'fontFamily': 'Roboto, sans-serif', 'fontWeight': '500', **STYLE_NON_EDITABLE}),
                    dcc.Dropdown(
                        id='weather-presets',
                        options=[
                            {'label': 'Last 7 Days', 'value': '7days'},
                            {'label': 'Last 30 Days', 'value': '30days'},
                            {'label': 'Last Year', 'value': '1year'}
                        ],
                        value='7days',
                        style={'marginBottom': '20px', 'fontFamily': 'Roboto, sans-serif', 'borderRadius': '8px', 'borderColor': '#ced4da'},
                        className='custom-dropdown'
                    )
                ], width=6)
            ]),
            dbc.Label("Select Metrics", style={'color': '#333', 'fontFamily': 'Roboto, sans-serif', 'fontWeight': '500', **STYLE_NON_EDITABLE}),
            dcc.Checklist(
                id='weather-metrics',
                options=[
                    {'label': 'Temperature (°C)', 'value': 'temp'},
                    {'label': 'Humidity (%)', 'value': 'humidity'},
                    {'label': 'Wind Speed (m/s)', 'value': 'windspeed'}
                ],
                value=['temp'],  # Default value to ensure graph triggers
                style={'marginTop': '15px', 'marginBottom': '25px', 'fontFamily': 'Roboto, sans-serif'},
                inline=True,
                className='custom-checklist'
            ),
            dcc.Loading(
                id="loading-weather",
                children=[
                    html.Div(id='weather-output', style={'marginTop': '25px', 'marginBottom': '20px', **STYLE_NON_EDITABLE}),
                    dbc.Button("Retry", id='weather-retry-button', color='primary', 
                               style={'display': 'none', 'borderRadius': '8px', 'backgroundColor': '#00A1D6', 'borderColor': '#00A1D6'}),
                    dcc.Graph(id='weather-graph', style={'height': '450px', 'border': '1px solid #e9ecef', 'borderRadius': '8px', 'backgroundColor': '#ffffff'})
                ],
                type="circle", color='#00A1D6'
            ),
            dcc.Store(id='weather-data-store')
        ]), style={'boxShadow': '0 4px 12px rgba(0,0,0,0.1)', 'borderRadius': '12px', 'background': 'linear-gradient(135deg, #ffffff, #f0f4f8)', 'padding': '25px', **STYLE_NON_EDITABLE})

    elif tab_id == 'nav-settings':
        return dbc.Card(dbc.CardBody([
            html.H3("Settings", style={'color': '#0056D2', 'marginBottom': '25px', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}),
            html.P("Manage your session below:", style={'color': '#666', 'marginBottom': '20px', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}),
            dbc.Button("Logout", id='logout-button', color='danger', style={'marginTop': '15px', 'borderRadius': '8px'}),
        ]), style={'boxShadow': '0 4px 8px rgba(0,0,0,0.1)', 'borderRadius': '10px', 'background': 'linear-gradient(135deg, #ffffff, #f8f9fa)', **STYLE_NON_EDITABLE})

    return html.Div()

def process_file_upload(contents, filename):
    global uploaded_data_store
    if contents:
        _, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        try:
            if not filename.endswith('.csv'):
                return html.Div(html.P('Unsupported file format. Please upload a valid CSV file.', 
                                       style={'color': '#dc3545', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE), 
                               style=STYLE_NON_EDITABLE, **PROPS_NON_EDITABLE)
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            uploaded_data_store['data'] = df
            power_cols = [col for col in df.columns if 'chiller' in col.lower() and 'power' in col.lower()]
            supply_cols = [col for col in df.columns if ('supply' in col.lower() or 'chws' in col.lower()) and ('temp' in col.lower() or 't' in col.lower())]
            return_cols = [col for col in df.columns if ('return' in col.lower() or 'chwr' in col.lower() or 'ret' in col.lower()) and ('temp' in col.lower() or 't' in col.lower())]
            return html.Div([
                html.P(f'Successfully uploaded: {filename}', style={'fontWeight': 'bold', 'color': '#333', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
                html.P(f'Dataset has {len(df)} rows and {len(df.columns)} columns.', style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
                html.P(f"Detected Chiller Power columns: {', '.join(power_cols) if power_cols else 'None'}", style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
                html.P(f"Detected Supply Temp columns: {', '.join(supply_cols) if supply_cols else 'None'}", style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
                html.P(f"Detected Return Temp columns: {', '.join(return_cols) if return_cols else 'None'}", style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
                html.P(f"All columns in dataset: {', '.join(df.columns)}", style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE)
            ], style=STYLE_NON_EDITABLE, **PROPS_NON_EDITABLE)
        except Exception as e:
            return html.Div([html.P('There was an error processing the file.', style={'color': '#dc3545', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
                             html.P(str(e), style={'color': '#dc3545', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE)], 
                           style=STYLE_NON_EDITABLE, **PROPS_NON_EDITABLE)
    return html.Div([html.P('Previously uploaded file is still available.', style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE),
                    html.P(f'Dataset has {len(uploaded_data_store["data"])} rows and {len(uploaded_data_store["data"].columns)} columns.', 
                           style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE)], 
                   style=STYLE_NON_EDITABLE, **PROPS_NON_EDITABLE) if 'data' in uploaded_data_store else \
           html.P('No file uploaded yet.', style={'color': '#666', 'fontFamily': 'Roboto, sans-serif', **STYLE_NON_EDITABLE}, **PROPS_NON_EDITABLE)