# Data Consumption Tool Dashboard

The Data Consumption Tool is a web-based dashboard application built using Flask and Dash, designed to visualize and analyze chiller performance data and weather data for Hyderabad, India. It provides an interactive interface for users to upload CSV datasets, view chiller power and temperature metrics, and explore historical weather data fetched from the Visual Crossing Weather API. The application is styled with Bootstrap and uses the Roboto font for a clean, modern look.

Features
1. User Authentication
Login Page: Users must log in with a username (Rohith) and password (password123) to access the dashboard. The login state is managed using Flask's session handling.
Logout Functionality: Users can log out from the settings tab, redirecting them to the login page.
2. Navigation
Tabs: The dashboard includes four main tabs:
Dashboard: Displays visualizations of uploaded chiller data.
Data Upload: Allows users to upload CSV files containing chiller data.
Weather: Fetches and displays weather data for Hyderabad, India.
Settings: Provides a logout option.
Responsive Navigation: Tabs are styled with active/inactive states and a modern design using Bootstrap and custom CSS.
3. Data Upload
File Upload: Users can upload CSV files (e.g., chiller performance data) via a drag-and-drop interface.
Reset Option: A reset button clears the uploaded dataset.
Validation: Only CSV files are supported, with feedback provided on successful uploads or errors.
Data Storage: Uploaded data is stored in memory using a global dictionary (uploaded_data_store).
4. Dashboard Visualizations
Chiller Data Visualization: Displays line graphs for:
Chiller Power: Power consumption (kW) of chillers.
Supply Temperature: Chiller water supply temperature (°C).
Return Temperature: Chiller water return temperature (°C).
Dynamic Column Detection: Automatically identifies relevant columns in the uploaded CSV based on keywords (e.g., "chiller", "power", "supply", "return").
Interactive Checklists: Users can select which columns to visualize using checklists.
Data Sampling: Limits the number of data points to 1000 for performance, using uniform sampling if needed.
5. Weather Data
API Integration: Fetches historical weather data for Hyderabad, India from the Visual Crossing Weather API.
Date Range Selection: Users can specify a custom date range (up to the current date, March 19, 2025) or use presets (7 days, 30 days, 1 year).
Metrics: Visualizes temperature (°C), humidity (%), and wind speed (m/s) in an interactive line graph.
Caching: Weather API calls are cached for 1 hour to reduce redundant requests.
Error Handling: Displays alerts for invalid dates, API errors (e.g., rate limits), or future date selections.
6. Styling and Usability
Bootstrap: Uses dash-bootstrap-components for responsive layouts and card-based design.
Roboto Font: Applied via an external stylesheet for a consistent typography.
Custom CSS: Enhances the weather section's date picker, dropdown, and checklist with modern styling (see custom.css).
Non-Editable Elements: UI elements are locked to prevent accidental edits using custom styles and properties.

Project Structure
app.py: Main Flask application file that initializes the server, Dash apps (login and dashboard), and defines routes (/, /login, /dashboard, /logout).
dashboard_app.py: Configures the Dash dashboard app, including layout, callbacks for tab navigation, data upload, weather fetching, and graph rendering.
login_app.py: Configures the Dash login app with a simple username/password form and authentication logic.
sample_data.csv: Example CSV file with chiller performance data (power, supply/return temperatures) from July 20, 2023, to October 5, 2023.
custom.css: Custom styles for the weather section's UI components.

Dependencies
Python 3.x
Flask
Dash
dash-bootstrap-components
pandas
plotly.express
requests
flask-caching
base64, io (for file handling)

Install dependencies using:
pip install flask dash dash-bootstrap-components pandas plotly requests flask-caching
