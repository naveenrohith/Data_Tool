from flask import Flask, redirect, session
from dash import Dash, html
import dash_bootstrap_components as dbc
import os

# Initialize Flask server
server = Flask(__name__)
server.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')  

# Set the weather API key as an environment variable
os.environ['WEATHER_API_KEY'] = '6K9Z93LW56Z4TWPWWVN5DW2M4'  # Ideally set this in your system environment, not hardcoded

# Define constant for login route
LOGIN_PATH = '/login'  

# Initialize Dash apps for login and dashboard with Bootstrap styling
login_app = Dash(__name__, server=server, url_base_pathname=LOGIN_PATH + '/', 
                 external_stylesheets=[dbc.themes.BOOTSTRAP])
dashboard_app = Dash(__name__, server=server, url_base_pathname='/dashboard/', 
                     external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

# Import and setup app configurations from separate modules
from login_app import setup_login_app
from dashboard_app import setup_dashboard_app

# Configure login app
setup_login_app(login_app)
# Configure dashboard app
setup_dashboard_app(dashboard_app)

# Route handler for root URL
@server.route('/')
def home():
    return redirect(LOGIN_PATH)

# Route handler for login page
@server.route(LOGIN_PATH)
def login():
    return login_app.index()

# Route handler for dashboard main page
@server.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(LOGIN_PATH)
    return dashboard_app.index()

# Route handler for dashboard sub-paths
@server.route('/dashboard/<path:path>')
def serve_dashboard(path):
    if not session.get('logged_in'):
        return redirect(LOGIN_PATH)
    return dashboard_app.index()

# Route handler for logout
@server.route('/logout')
def logout():
    session.pop('logged_in', None)  # Clear the logged-in status
    return redirect(LOGIN_PATH)

# Main entry point for running the application
if __name__ == '__main__':
    server.run(debug=True)