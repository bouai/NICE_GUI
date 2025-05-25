# -------------------------------------------
# Imports and Constants
# -------------------------------------------
from nicegui import ui
import sqlite3
import json
import pandas as pd

# Database and table configuration
DB_PATH = 'data/KYC_DataBase.db'
TABLE_NAME_1 = 'OnboardingData'
TABLE_NAME_2 = 'KycRefreshData'
TABLE_NAME_3 = 'log' 
ITEMS_PER_PAGE = 5

# -------------------------------------------
# Dashboard State and Filter Inputs
# -------------------------------------------
# Store dashboard state for pagination and filters
dashboard_state = {
    'page': 1,
    'name': '',
    'material': '',
    'status': '',
    'case_id': '',
    'data_source': '',
}

# Global dictionary to store input fields for filters
filter_inputs = {}

# -------------------------------------------
# Data Fetching and Processing Functions
# -------------------------------------------
def get_data():
    """Fetch and merge onboarding and refresh data from the database, format dates, and ensure string types."""
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            f"""
            SELECT
                id,
                entity_legal_name,
                client_identifier,
                document_name,  
                material_changename,
                refresh_status,
                KycRefresh_created_date,
                KycRefresh_created_date AS sla_start_date,
                KycRefresh_updated_date
            FROM {TABLE_NAME_2}
            """, conn)
    # Ensure string types for relevant columns
    for col in ['entity_legal_name', 'material_changename', 'refresh_status','document_name']:
        if col in df.columns:
            df[col] = df[col].astype(str)
    # Format and calculate date columns
    df['KycRefresh_created_date'] = pd.to_datetime(df['KycRefresh_created_date'], errors='coerce')
    df['sla_start_date'] = pd.to_datetime(df['sla_start_date'], errors='coerce')
    df['case_sla_date'] = df['sla_start_date'] + pd.Timedelta(days=90)
    df['KycRefresh_updated_date'] = pd.to_datetime(df['KycRefresh_updated_date'], errors='coerce')
    # Format dates as strings and fill missing values
    for col in ['KycRefresh_created_date', 'case_sla_date', 'KycRefresh_updated_date']:
        df[col] = df[col].dt.strftime('%Y-%m-%d').fillna('N/A')
    return df

def filter_df(df, name, material, status, case_id, data_source):
    """Apply filters to the dataframe based on user input."""
    if name:
        df = df[df['entity_legal_name'].str.contains(name, case=False, na=False)]
    if material:
        df = df[df['material_changename'].str.contains(material, case=False, na=False)]
    if status:
        df = df[df['refresh_status'].str.contains(status, case=False, na=False)]
    if case_id:
        df = df[df['client_identifier'].str.contains(case_id, case=False, na=False)]
    if data_source:
        df = df[df['document_name'].str.contains(data_source, case=False, na=False)]
    return df

def update_data_table():
    """Update the data table dynamically based on the current filters and pagination state."""
    df = get_data()
    filtered = filter_df(
        df,
        dashboard_state['name'],
        dashboard_state['material'],
        dashboard_state['status'],
        dashboard_state['case_id'],
        dashboard_state['data_source'],
    )
    total_pages = max(1, (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    dashboard_state['page'] = max(1, min(dashboard_state['page'], total_pages))
    paginated = filtered.iloc[(dashboard_state['page']-1)*ITEMS_PER_PAGE:dashboard_state['page']*ITEMS_PER_PAGE]

    # Clear and update the data table UI
    data_table.clear()
    for _, row in paginated.iterrows():
        with data_table:
            with ui.row().classes('border-b p-3 items-center hover:bg-gray-50 transition-all rounded-lg'):
                ui.link(row['entity_legal_name'], f'/client/{row["id"]}').classes('text-blue-600 font-medium underline w-40 text-center')
                
                # Display material change as Yes/No
                material_change_value = row.get('material_changename', None)
                val = str(material_change_value).strip().lower()
                if not val or val in ('none', 'nan', 'null', '0'):
                    material_change_display = "No"
                else:
                    material_change_display = "Yes"
                ui.label(material_change_display).classes('w-40 text-center text-gray-700')
                
                # Display refresh status as a button with color coding
                refresh_status_value = get_refresh_status(row['client_identifier'])
                if refresh_status_value == '1':
                    refresh_status_display = "KYC Refresh is triggered"
                    button_classes = 'w-40 text-center bg-blue-500 text-white hover:bg-blue-600'
                elif refresh_status_value == '0':
                    refresh_status_display = "Profile Updates Absorbed"
                    button_classes = 'w-40 text-center bg-green-500 text-white hover:bg-green-600'
                else:
                    refresh_status_display = "KYC Refresh Not Triggered"
                    button_classes = 'w-40 text-center bg-gray-400 text-white hover:bg-gray-500'

                ui.button(
                    refresh_status_display,
                    on_click=lambda client_id=row['id']: ui.navigate.to(f'/client/{client_id}')
                ).classes(button_classes)

                ui.label(row.get('client_identifier', '')).classes('w-40 text-center text-gray-700')
                
                doc_val = row.get('document_name', '')
                ui.label(doc_val if doc_val and str(doc_val).strip() else 'N/A').classes('w-40 text-center text-gray-700')
                
                ui.label(str(row.get('KycRefresh_created_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('case_sla_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('KycRefresh_updated_date', ''))[:10]).classes('w-40 text-center text-gray-700')

    # Update pagination controls
    pagination_label.set_text(f"Page {dashboard_state['page']} of {total_pages}")
    if dashboard_state['page'] == 1:
        prev_button.disable()
    else:
        prev_button.enable()

    if dashboard_state['page'] == total_pages:
        next_button.disable()
    else:
        next_button.enable()

# -------------------------------------------
# Agent Data Extraction and Parsing Functions
# -------------------------------------------
def parse_step(step_str):
    """Parse a step string to extract the step name and agent name."""
    if " (" in step_str and step_str.endswith(")"):
        step_name, agent_part = step_str.rsplit(" (", 1)
        agent_name = agent_part[:-1]  # Remove the closing ")"
        return step_name, agent_name
    return step_str, None

def get_agent_data(client_identifier):
    """Fetch and aggregate agent log data for a given client_identifier."""
    conn = sqlite3.connect(DB_PATH)
    query = f"""
    SELECT steps
    FROM {TABLE_NAME_3}
    WHERE [client_identifier] = ?
    """
    df = pd.read_sql_query(query, conn, params=(client_identifier,))
    agent_data = {}
    for idx, row in df.iterrows():
        try:
            steps_data = json.loads(row["steps"])
            if isinstance(steps_data, list):
                for step in steps_data:
                    step_str = step.get("step", "")
                    step_name, agent_name = parse_step(step_str)
                    if agent_name:
                        if agent_name not in agent_data:
                            agent_data[agent_name] = {
                                'total_jobs': 0,
                                'total_time': 0,
                                'tools_called': [],
                                'scores': []
                            }
                        agent_data[agent_name]['total_jobs'] += 1
                        agent_data[agent_name]['total_time'] += step.get('duration_sec', 0)
                        # Maintain order and uniqueness for tools called
                        if step_name not in agent_data[agent_name]['tools_called']:
                            agent_data[agent_name]['tools_called'].append(step_name)
                        score = step.get('score', None)
                        if score is not None:
                            agent_data[agent_name]['scores'].append(score)
        except Exception as e:
            ui.notify(f"Error parsing steps JSON: {e}", color='negative')
    conn.close()
    # Post-process agent data for display
    for agent in agent_data:
        agent_data[agent]['total_time'] = round(agent_data[agent]['total_time'], 2)
        # Show all tools called as a comma-separated string
        agent_data[agent]['tool_called'] = ', '.join(agent_data[agent]['tools_called']) if agent_data[agent]['tools_called'] else 'N/A'
        if agent_data[agent]['scores']:
            agent_data[agent]['accuracy'] = round(sum(agent_data[agent]['scores']) / len(agent_data[agent]['scores']), 2)
        else:
            agent_data[agent]['accuracy'] = 'N/A'
        del agent_data[agent]['tools_called']
        del agent_data[agent]['scores']
    return agent_data

def get_criminal_scan_result(client_identifier):
    """Fetch the 'result' from the 'Scan Profiles (Screening Agent)' step for a client."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT steps FROM {TABLE_NAME_3} WHERE client_identifier = ?", (client_identifier,))
        rows = cur.fetchall()
        for row in rows:
            try:
                steps = json.loads(row[0])
                if isinstance(steps, list):
                    for step in steps:
                        if step.get("step") == "Scan Profiles (Screening Agent)":
                            return step.get("result", "N/A")
            except Exception:
                continue
    return "N/A"

# -------------------------------------------
# Dashboard Page UI Construction
# -------------------------------------------
def dashboard_page():
    """Construct the main dashboard page UI, including filters, data table, and pagination."""
    df = get_data()
    filtered = filter_df(
        df,
        dashboard_state['name'],
        dashboard_state['material'],
        dashboard_state['status'],
        dashboard_state['case_id'],
        dashboard_state['data_source'],
    )
    total_pages = max(1, (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    dashboard_state['page'] = max(1, min(dashboard_state['page'], total_pages))
    paginated = filtered.iloc[(dashboard_state['page']-1)*ITEMS_PER_PAGE:dashboard_state['page']*ITEMS_PER_PAGE]

    # Dashboard Header Section
    with ui.element('div').classes('bg-gradient-to-r from-blue-600 to-blue-800 text-white p-6 rounded-lg shadow-lg mb-6 w-full'):
        ui.label('KYC Refresh Dashboard').classes('text-3xl font-semibold text-center')
        ui.label('KYC Review process: Intelligent Automation using AI agents').classes('text-lg text-center mt-2')

    # Filter Controls Section
    with ui.card().classes('mb-6 p-6 bg-white rounded-lg shadow-md border border-gray-200'):
        ui.label('Filter Controls').classes('text-xl font-semibold text-gray-800 mb-4')
        with ui.row().classes('gap-4 flex-wrap'):
            filter_inputs['name'] = ui.input('Client Name', value=dashboard_state['name']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            filter_inputs['material'] = ui.input('Material Change', value=dashboard_state['material']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            # Removed the Refresh Status filter input
            # filter_inputs['status'] = ui.input('Refresh Status', value=dashboard_state['status']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            filter_inputs['case_id'] = ui.input('Case ID', value=dashboard_state['case_id']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            filter_inputs['data_source'] = ui.input('Data Source', value=dashboard_state['data_source']).props('clearable outlined dense').classes('w-56 bg-gray-50')

            def apply_filters():
                """Apply the filters and update the data table."""
                dashboard_state['name'] = filter_inputs['name'].value
                dashboard_state['material'] = filter_inputs['material'].value
                # dashboard_state['status'] = filter_inputs['status'].value  # Removed
                dashboard_state['case_id'] = filter_inputs['case_id'].value
                dashboard_state['data_source'] = filter_inputs['data_source'].value
                dashboard_state['page'] = 1  # Reset to the first page
                update_data_table()

            def reset_filters():
                """Reset the filters and update the data table."""
                dashboard_state.update({'name': '', 'material': '', 'status': '', 'case_id': '', 'data_source': '', 'page': 1})
                filter_inputs['name'].set_value('')
                filter_inputs['material'].set_value('')
                # filter_inputs['status'].set_value('')  # Removed
                filter_inputs['case_id'].set_value('')
                filter_inputs['data_source'].set_value('')
                update_data_table()

            with ui.row().classes('gap-4'):
                ui.button('Apply Filters', on_click=apply_filters).classes('bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition')
                ui.button('Reset Filters', on_click=reset_filters).classes('bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 transition')

    # Data Table Section
    global data_table
    with ui.card().classes('mb-6 p-6 bg-white rounded-lg shadow-md border border-gray-200'):
        ui.label('KYC Data Overview').classes('text-xl font-semibold text-gray-800 mb-4')
        with ui.row().classes('bg-blue-50 font-semibold p-3 rounded-md shadow-sm text-gray-800'):
            for col in ['Client Name', 'Material Change', 'Refresh Status', 'Case ID', 'Data Source', 'KYC Creation Date', 'Case SLA Date', 'KYC Updated Date']:
                ui.label(col).classes('w-40 text-center')  # Ensure consistent width for all columns
        
        data_table = ui.column()

    for _, row in paginated.iterrows():
        with data_table:
            with ui.row().classes('border-b p-3 items-center hover:bg-gray-50 transition-all rounded-lg'):
                ui.link(row['entity_legal_name'], f'/client/{row["id"]}').classes('text-blue-600 font-medium underline w-40 text-center')
                
                # Display material change as Yes/No
                material_change_value = row.get('material_changename', None)
                val = str(material_change_value).strip().lower()
                if not val or val in ('none', 'nan', 'null', '0'):
                    material_change_display = "No"
                else:
                    material_change_display = "Yes"
                ui.label(material_change_display).classes('w-40 text-center text-gray-700')
                
                # Display refresh status as a button with color coding
                refresh_status_value = get_refresh_status(row['client_identifier'])
                if refresh_status_value == '1':
                    refresh_status_display = "KYC Refresh is triggered"
                    button_classes = 'w-40 text-center bg-blue-500 text-white hover:bg-blue-600'
                elif refresh_status_value == '0':
                    refresh_status_display = "Profile Updates Absorbed"
                    button_classes = 'w-40 text-center bg-green-500 text-white hover:bg-green-600'
                else:
                    refresh_status_display = "KYC Refresh Not Triggered"
                    button_classes = 'w-40 text-center bg-gray-400 text-white hover:bg-gray-500'

                ui.button(
                    refresh_status_display,
                    on_click=lambda client_id=row['id']: ui.navigate.to(f'/client/{client_id}')
                ).classes(button_classes)

                ui.label(row.get('client_identifier', '')).classes('w-40 text-center text-gray-700')
                
                doc_val = row.get('document_name', '')
                ui.label(doc_val if doc_val and str(doc_val).strip() else 'N/A').classes('w-40 text-center text-gray-700')
                
                ui.label(str(row.get('KycRefresh_created_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('case_sla_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('KycRefresh_updated_date', ''))[:10]).classes('w-40 text-center text-gray-700')

    # Pagination Controls Section
    with ui.row().classes('mt-4 justify-center items-center'):
        def prev_page():
            """Navigate to the previous page and update the data table."""
            if dashboard_state['page'] > 1:
                dashboard_state['page'] -= 1
                update_data_table()

        def next_page():
            """Navigate to the next page and update the data table."""
            dashboard_state['page'] += 1
            update_data_table()

        global prev_button, next_button, pagination_label
        prev_button = ui.button('Previous', on_click=prev_page).classes('bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition')
        pagination_label = ui.label(f'Page {dashboard_state["page"]} of {total_pages}').classes('mx-4 text-lg text-gray-700')
        next_button = ui.button('Next', on_click=next_page).classes('bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition')

        if dashboard_state['page'] <= 1:
            prev_button.disable()
        if dashboard_state['page'] >= total_pages:
            next_button.disable()

# -------------------------------------------
# Utility Function to Fetch Refresh Status
# -------------------------------------------
def get_refresh_status(client_identifier):
    """Fetch the latest refresh_status from KycRefreshData for a given client_identifier."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT refresh_status FROM KycRefreshData WHERE client_identifier = ?", (client_identifier,))
        result = cur.fetchone()
        return str(result[0]) if result else ''

# -------------------------------------------
# Main Dashboard Page Route
# -------------------------------------------
@ui.page('/')
def main_dashboard():
    """Route for the main dashboard page."""
    dashboard_page()

# -------------------------------------------
# Client Detail Page Route and UI
# -------------------------------------------
@ui.page('/client/{client_id}')
def client_detail(client_id: int):
    """
    Route for the client detail page.
    Displays onboarding, refresh, screening, and agent log details for a specific client.
    """
    # Retrieve client details from the KycRefreshData table using id
    with sqlite3.connect(DB_PATH) as conn:
        refresh_df = pd.read_sql_query(
            "SELECT * FROM KycRefreshData WHERE id = ?",
            conn,
            params=(client_id,)
        )

    if refresh_df.empty:
        refresh_data = {
            'entity_legal_name': 'N/A',
            'client_identifier': 'N/A',
            'document_name': 'N/A',
            'country_issuing_id': 'N/A',
            'refresh_status': 'N/A',
            'material_changename': 'N/A',
            'KycRefresh_created_date': 'N/A',
            'KycRefresh_updated_date': 'N/A',
        }
    else:
        refresh_data = refresh_df.iloc[0].to_dict()

    # Use the correct client_identifier for agent logs and onboarding lookup
    client_identifier = refresh_data.get('client_identifier', 'N/A')

    # Fetch onboarding data from OnboardingData using client_identifier
    with sqlite3.connect(DB_PATH) as conn:
        onboarding_df = pd.read_sql_query(
            "SELECT * FROM OnboardingData WHERE client_identifier = ?",
            conn,
            params=(client_identifier,)
        )
    if onboarding_df.empty:
        onboarding_data = {
            'entity_legal_name': 'N/A',
            'client_identifier': 'N/A',
            'member_type': 'N/A',
            'country_issuing_id': 'N/A',
            'document_name': 'N/A',
        }
    else:
        onboarding_data = onboarding_df.iloc[0].to_dict()

    # Dummy data for screening agent results (for demonstration)
    with sqlite3.connect(DB_PATH) as conn:
        screening_df = pd.read_sql_query(
            "SELECT screening_agent_status FROM KycRefreshData WHERE client_identifier = ? ORDER BY id DESC LIMIT 1",
            conn,
            params=(client_identifier,)
        )
    screening_data = {
        'screening_agent_status': screening_df['screening_agent_status'] if not screening_df.empty else '0',
        'adverse_media_result': '0',
    }

    # -------------------------------
    # UI Layout for Client Detail Page
    # -------------------------------

    # Header Section
    with ui.element('div').classes('bg-gradient-to-r from-blue-600 to-blue-800 text-white p-8 rounded-xl shadow-2xl mb-8 w-full'):
        ui.label(onboarding_data['entity_legal_name']).classes('text-4xl font-bold text-center tracking-tight')
        ui.label('KYC Review Process: Intelligent Automation Using AI Agents').classes('text-xl text-center mt-2 opacity-90')

    with ui.element('div').classes('container mx-auto px-4'):
        # First Row: Onboarding and KYC Refresh Details
        ui.label('Client KYC Details').classes('text-2xl font-semibold text-blue-600 mb-4')  # Title for the first row
        with ui.element('div').classes('grid grid-cols-1 md:grid-cols-2 gap-6 mb-8'):
            # Onboarding Details Card
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Existing Details').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.column().classes('gap-1'):
                    ui.label(f"Client Name: {onboarding_data['entity_legal_name']}").classes('text-lg text-gray-600 font-medium')
                    ui.label(f"Client Identifier: {onboarding_data.get('client_identifier', 'N/A')}").classes('text-lg text-gray-600')
                    ui.label(f"Client Type: {onboarding_data.get('member_type', 'N/A')}").classes('text-lg text-gray-600')
                    ui.label(f"Client Domicile Country: {onboarding_data.get('country_issuing_id', 'N/A')}").classes('text-lg text-gray-600')
                    ui.label(f"Client Documents: {onboarding_data.get('document_name', 'N/A')}").classes('text-lg text-gray-600')

            # Refresh Details Card
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Refresh Details').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.row().classes('gap-2'):  # Create a row to split content into two sections
                    # Basic Refresh Info
                        with ui.column().classes('gap-1 w-5/9'):  # Left section takes half the width
                            ui.label(f"Client Name: {refresh_data.get('entity_legal_name', 'N/A')}").classes('text-lg text-gray-600 font-medium')
                            ui.label(f"Client Identifier: {refresh_data.get('client_identifier', 'N/A')}").classes('text-lg text-gray-600')
                            ui.label(f"Client Type: {refresh_data.get('member_type', 'N/A')}").classes('text-lg text-gray-600')
                            ui.label(f"Client Domicile Country: {refresh_data.get('country_issuing_id', 'N/A')}").classes('text-lg text-gray-600')
                            ui.label(f"Client Documents: {refresh_data.get('document_name', 'N/A')}").classes('text-lg text-gray-600')
                                 
        # Second Row: Materiality, Screening, Agents Performance
        ui.label('Additional Details').classes('text-2xl font-semibold text-blue-600 mb-4')  # Title for the second row
        with ui.element('div').classes('grid grid-cols-1 lg:grid-cols-3 gap-6'):
            # Materiality Card
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Researcher Agent').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.column().classes('gap-3'):
                    # 1. Materiality Hit logic
                    material_change_val = refresh_data.get('material_changename', '')
                    if material_change_val and str(material_change_val).strip() != '' and str(material_change_val).strip() != '0':
                        materiality_hit = "Yes"
                    else:
                        materiality_hit = "No"
                    ui.label(f"Materiality Hit: {materiality_hit}").classes('text-lg text-gray-600 font-medium')

                    # Display material changes
                    with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 mt-4 w-full'):
                        ui.label('Material Changes:').classes('text-lg font-semibold text-gray-600')
                        with ui.column().classes('gap-2 pl-10'):
                            for _, row in refresh_df.iterrows():
                                mat_val = row.get('material_changename', '')
                                # Show string if present and not '0', else show N/A
                                if mat_val and str(mat_val).strip() != '' and str(mat_val).strip() != '0':
                                    mat_val_display = str(mat_val)
                                else:
                                    mat_val_display = 'N/A'
                                ui.label(f"Material Change: {mat_val_display}").classes('text-sm text-gray-500')

                    # Conditional UI card based on Materiality Hit
                    if refresh_data.get('material_changename', 'NO') == 'YES':
                        # Red card for "Outreach Called: YES"
                        with ui.row().classes('justify-center items-center mt-4 w-full'):  # Center-align the card
                            with ui.card().classes('p-4 bg-red-100 rounded-lg shadow-sm border border-red-200'):
                                ui.label('Outreach Called: YES').classes('text-lg font-semibold text-red-800')
                    else:
                        # Green card for "Outreach Called: NO"
                        with ui.row().classes('justify-center items-center mt-4 w-full'):  # Center-align the card
                            with ui.card().classes('p-4 bg-green-100 rounded-lg shadow-sm border border-green-200'):
                                ui.label('Outreach Called: NO').classes('text-lg font-semibold text-green-800')

            # Screening Card
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Screening Agent').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200 ')
                with ui.column().classes('gap-3'):

                    # Extract and normalize the status
                    opac_status_raw = screening_data.get('screening_agent_status', '')
                    search_status_raw = screening_data.get('adverse_media_result', '')
                    screening_status = str(opac_status_raw).strip() if opac_status_raw is not None else ''
                    adverse_search_status = str(search_status_raw).strip() if search_status_raw is not None else ''
                    
                    # Get hit_details from TABLE_NAME_3
                    hit_details = get_criminal_scan_result(client_identifier)
                    search_details = adverse_search_status if adverse_search_status and adverse_search_status != '0' else 'TBD'
                    # Determine display values
                    opac_hit = 'YES' if screening_status and screening_status != '0' else 'NO'
                    # OPAC Hit Card
                    with ui.row().classes('justify-center mt-4'):
                        with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 mt-4 w-full'):
                            ui.label(f"OFAC Hit: {opac_hit}").classes('text-lg font-semibold text-gray-600 justify-center items-center')
                            with ui.row():
                                ui.label("Hit Details:").classes('font-bold')
                                ui.label(hit_details)

                    # Adverse Media Search Card
                    with ui.row().classes('justify-center items-center mt-4 w-full'):
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 mt-4 w-full'):
                            ui.label('Adverse Media Search').classes('text-lg font-semibold text-gray-600 justify-center items-center')
                            with ui.row():
                                ui.label("Hit Details:").classes('font-bold')
                                ui.label(search_details)

                    # Conditional Review Triggered Card
                    if opac_hit == 'YES':
                        with ui.row().classes('justify-center items-center mt-4 w-full'):  # Center-align the card
                            with ui.card().classes('p-4 bg-red-100 rounded-lg shadow-sm border border-red-200'):
                                ui.label('Review Triggered').classes('text-lg font-semibold text-red-800')
                    else:
                        with ui.row().classes('justify-center items-center mt-4 w-full'):  # Center-align the card
                            with ui.card().classes('p-4 bg-green-100 rounded-lg shadow-sm border border-green-200'):
                                ui.label('Review Not Triggered').classes('text-lg font-semibold text-green-800')

            # Agents Performance Card
            # Fetch agent data for a specific client
            agent_data = get_agent_data(client_identifier)

            # Agents Performance Card
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Agent Logs').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.column().classes('gap-3'):
                    with ui.row().classes('justify-center items-center mt-4 w-full'):
                        # Researcher Agent Card
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 w-full'):
                            researcher_data = agent_data.get('Researcher Agent', {})
                            ui.label(f"Researcher Agent     |     Total Jobs: 3").classes('text-lg font-semibold text-gray-600')
                            with ui.column().classes('gap-1 pl-4'):
                                with ui.row():
                                    ui.label("Time Taken (Sec):").classes('font-bold')
                                    ui.label(f"{researcher_data.get('total_time', 'N/A')}")
                                with ui.row():
                                    ui.label("Steps Taken:").classes('font-bold')
                                    steps = researcher_data.get('tool_called', 'N/A')
                                    if steps != 'N/A':
                                        steps_bullets = '• ' + '\n• '.join(steps.split(', '))
                                    else:
                                        steps_bullets = 'N/A'
                                    ui.label(steps_bullets).style('white-space: pre-line;')
                                with ui.row():
                                    ui.label("Precision:").classes('font-bold')
                                    ui.label(f"{researcher_data.get('accuracy', 'N/A')}")

                        # KYC Analyst Agent Card
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 w-full'):
                            kyc_data = agent_data.get('Analyst Agent', {})
                            ui.label(f"KYC Analyst Agent     |     Total Jobs: 1").classes('text-lg font-semibold text-gray-600 mt-2')
                            with ui.column().classes('gap-1 pl-4'):
                                with ui.row():
                                    ui.label("Time Taken (Sec):").classes('font-bold')
                                    ui.label(f"{kyc_data.get('total_time', 'N/A')}")
                                with ui.row():
                                    ui.label("Steps Taken:").classes('font-bold')
                                    steps = kyc_data.get('tool_called', 'N/A')
                                    if steps != 'N/A':
                                        steps_bullets = '• ' + '\n• '.join(steps.split(', '))
                                    else:
                                        steps_bullets = 'N/A'
                                    ui.label(steps_bullets).style('white-space: pre-line;')
                                with ui.row():
                                    ui.label("Record Insertion Accuracy:").classes('font-bold')
                                    ui.label(f"{kyc_data.get('accuracy', 'N/A')}")

                        # Screening Agent Card
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 w-full'):
                            screening_data = agent_data.get('Screening Agent', {})
                            ui.label(f"Screening Agent     |     Total Jobs: 2").classes('text-lg font-semibold text-gray-600 mt-2')
                            with ui.column().classes('gap-1 pl-4'):
                                with ui.row():
                                    ui.label("Time Taken (Sec):").classes('font-bold')
                                    ui.label(f"{screening_data.get('total_time', 'N/A')}")
                                with ui.row():
                                    ui.label("Steps Taken:").classes('font-bold')
                                    steps = screening_data.get('tool_called', 'N/A')
                                    if steps != 'N/A':
                                        steps_bullets = '• ' + '\n• '.join(steps.split(', '))
                                    else:
                                        steps_bullets = 'N/A'
                                    ui.label(steps_bullets).style('white-space: pre-line;')
                                with ui.row():
                                    ui.label("Hit Detection Precision:").classes('font-bold')
                                    ui.label(f"{screening_data.get('accuracy', 'N/A')}")
# -------------------------------------------
# Run the NiceGUI App
# -------------------------------------------
ui.run(reload=False)