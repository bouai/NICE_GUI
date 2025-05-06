from nicegui import ui
import sqlite3
import pandas as pd

DB_PATH = 'Data/KYC_DataBase.db'
TABLE_NAME = 'OnboardingData'
ITEMS_PER_PAGE = 5

# Store dashboard state
dashboard_state = {
    'page': 1,
    'name': '',
    'material': '',
    'status': '',
    'case_id': '',
    'data_source': '',
}

# Global dictionary to store input fields
filter_inputs = {}

def get_data():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
    for col in ['entity_legal_name', 'refresh_status', 'outreach_agent_status', 'document_name']:
        if col in df.columns:
            df[col] = df[col].astype(str)
    if 'onboarding_created_date' in df.columns:
        df['onboarding_created_date'] = pd.to_datetime(df['onboarding_created_date'], errors='coerce')
        df['case_sla_date'] = df['onboarding_created_date'] + pd.Timedelta(days=90)
    else:
        df['case_sla_date'] = ''
    return df

def filter_df(df, name, material, status, case_id, data_source):
    if name:
        df = df[df['entity_legal_name'].str.contains(name, case=False, na=False)]
    if material:
        df = df[df['refresh_status'].str.contains(material, case=False, na=False)]
    if status:
        df = df[df['outreach_agent_status'].str.contains(status, case=False, na=False)]
    if case_id:
        df = df[df['client_identifier'].str.contains(case_id, case=False, na=False)]
    if data_source:
        df = df[df['document_name'].str.contains(data_source, case=False, na=False)]
    return df

def update_data_table():
    """Update the data table dynamically based on the current filters."""
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

    # Clear and update the data table
    data_table.clear()
    for _, row in paginated.iterrows():
        with data_table:
            with ui.row().classes('border-b p-3 items-center hover:bg-gray-50 transition-all rounded-lg'):
                ui.link(row['entity_legal_name'], f'/client/{row["id"]}').classes('text-blue-600 font-medium underline w-40 text-center')
                ui.label(row.get('refresh_status', '')).classes('w-40 text-center text-gray-700')
                ui.label(row.get('outreach_agent_status', '')).classes('w-40 text-center text-gray-700')
                ui.label(row.get('client_identifier', '')).classes('w-40 text-center text-gray-700')
                ui.label(row.get('document_name', '')).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('onboarding_created_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('case_sla_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('onboarding_updated_date', ''))[:10]).classes('w-40 text-center text-gray-700')

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

def dashboard_page():
    df = get_data()
    filtered = filter_df(
        df,
        dashboard_state['name'],
        dashboard_state['material'],
        dashboard_state['status'],  # Corrected closing bracket
        dashboard_state['case_id'],
        dashboard_state['data_source'],
    )
    total_pages = max(1, (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    dashboard_state['page'] = max(1, min(dashboard_state['page'], total_pages))
    paginated = filtered.iloc[(dashboard_state['page']-1)*ITEMS_PER_PAGE:dashboard_state['page']*ITEMS_PER_PAGE]

    # Dashboard Header
    with ui.element('div').classes('bg-gradient-to-r from-blue-600 to-blue-800 text-white p-6 rounded-lg shadow-lg mb-6 w-full'):
        ui.label('KYC Refresh Dashboard').classes('text-3xl font-semibold text-center')
        ui.label('KYC Review process: Intelligent Automation using AI agents').classes('text-lg text-center mt-2')

    # Filter Section
    with ui.card().classes('mb-6 p-6 bg-white rounded-lg shadow-md border border-gray-200'):
        ui.label('Filter Controls').classes('text-xl font-semibold text-gray-800 mb-4')
        with ui.row().classes('gap-4 flex-wrap'):
            filter_inputs['name'] = ui.input('Client Name', value=dashboard_state['name']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            filter_inputs['material'] = ui.input('Material Change', value=dashboard_state['material']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            filter_inputs['status'] = ui.input('Case Status', value=dashboard_state['status']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            filter_inputs['case_id'] = ui.input('Case ID', value=dashboard_state['case_id']).props('clearable outlined dense').classes('w-56 bg-gray-50')
            filter_inputs['data_source'] = ui.input('Data Source', value=dashboard_state['data_source']).props('clearable outlined dense').classes('w-56 bg-gray-50')

            def apply_filters():
                """Apply the filters and update the data table."""
                dashboard_state['name'] = filter_inputs['name'].value
                dashboard_state['material'] = filter_inputs['material'].value
                dashboard_state['status'] = filter_inputs['status'].value
                dashboard_state['case_id'] = filter_inputs['case_id'].value
                dashboard_state['data_source'] = filter_inputs['data_source'].value
                dashboard_state['page'] = 1  # Reset to the first page
                update_data_table()

            def reset_filters():
                """Reset the filters and update the data table."""
                dashboard_state.update({'name': '', 'material': '', 'status': '', 'case_id': '', 'data_source': '', 'page': 1})
                filter_inputs['name'].set_value('')
                filter_inputs['material'].set_value('')
                filter_inputs['status'].set_value('')
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
            for col in ['Client Name', 'Material Change', 'Case Status', 'Case ID', 'Data Source', 'Case Creation Date', 'Case SLA Date', 'Case Completion Date']:
                ui.label(col).classes('w-40 text-center')  # Ensure consistent width for all columns
        
        data_table = ui.column()

    for _, row in paginated.iterrows():
        with data_table:
            with ui.row().classes('border-b p-3 items-center hover:bg-gray-50 transition-all rounded-lg'):
                ui.link(row['entity_legal_name'], f'/client/{row["id"]}').classes('text-blue-600 font-medium underline w-40 text-center')
                ui.label(row.get('refresh_status', '')).classes('w-40 text-center text-gray-700')
                ui.label(row.get('outreach_agent_status', '')).classes('w-40 text-center text-gray-700')
                ui.label(row.get('client_identifier', '')).classes('w-40 text-center text-gray-700')
                ui.label(row.get('document_name', '')).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('onboarding_created_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('case_sla_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('onboarding_updated_date', ''))[:10]).classes('w-40 text-center text-gray-700')

    # Pagination Section
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

@ui.page('/')
def main_dashboard():
    dashboard_page()

@ui.page('/client/{client_id}')
def client_detail(client_id: int):
    # Retrieve client details from the OnboardingData table using client_id
    with sqlite3.connect(DB_PATH) as conn:
        onboarding_df = pd.read_sql_query(
            "SELECT * FROM OnboardingData WHERE id = ?",
            conn,
            params=(client_id,)
        )
    
    if onboarding_df.empty:
        onboarding_data = {
            'entity_legal_name': 'N/A',
            'client_identifier': 'N/A',
            'document_name': 'N/A',
            'country_issuing_id': 'N/A',
            'onboarding_created_date': 'N/A',
            'onboarding_updated_date': 'N/A',
        }
    else:
        onboarding_data = onboarding_df.iloc[0].to_dict()

    # Retrieve details from the KycRefreshData table using client_identifier as the foreign key
    client_identifier = onboarding_data.get('client_identifier', 'N/A')
    with sqlite3.connect(DB_PATH) as conn:
        refresh_df = pd.read_sql_query(
            "SELECT * FROM KycRefreshData WHERE client_identifier = ?",
            conn,
            params=(client_identifier,)
        )
    
    if refresh_df.empty:
        refresh_data = {
            'entity_legal_name': 'N/A',
            'client_identifier': 'N/A',
            'document_name': 'N/A',
            'country_issuing_id': 'N/A',
            'refresh_status': 'N/A',
            'onboarding_created_date': 'N/A',
            'onboarding_updated_date': 'N/A',
        }
    else:
        refresh_data = refresh_df.iloc[0].to_dict()

    # Page layout
    with ui.element('div').classes('bg-gradient-to-r from-blue-600 to-blue-800 text-white p-6 rounded-lg shadow-lg mb-6 w-full'):
        ui.label('Client Details').classes('text-3xl font-semibold text-center')
        ui.label('KYC Review process: Intelligent Automation using AI agents').classes('text-lg text-center mt-2')

    with ui.card().classes('p-6 bg-white rounded-lg shadow-md border border-gray-200 w-full'):
        # Center-align the row containing the cards
        with ui.row().classes('gap-8 w-full justify-center items-center'):
            # Left side: Onboarding Details
            with ui.card().classes('w-1/3 p-4 bg-gray-50 rounded-md shadow-sm border border-gray-200'):
                ui.label('Onboarding Details').classes('text-xl font-semibold text-gray-800 mb-4')
                with ui.column().classes('gap-2'):
                    with ui.row().classes('gap-4'):
                        ui.label(f"Client Name: {onboarding_data['entity_legal_name']}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Client Identifier: {onboarding_data.get('client_identifier', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Client Type: {onboarding_data.get('member_type', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Client Domicile Country: {onboarding_data.get('country_issuing_id', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Client Specific Documents: {onboarding_data.get('document_name', 'N/A')}").classes('text-lg text-gray-700')

            # Vertical separator
            ui.element('div').classes('w-px bg-gray-400 self-stretch')

            # Right side: KYC Refresh Details
            with ui.card().classes('w-1/3 p-4 bg-gray-50 rounded-md shadow-sm border border-gray-200'):
                ui.label('KYC Refresh Details').classes('text-xl font-semibold text-gray-800 mb-4')
                with ui.column().classes('gap-2'):
                    with ui.row().classes('gap-4'):
                        ui.label(f"Client Name: {refresh_data.get('entity_legal_name', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Client Identifier: {refresh_data.get('client_identifier', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Document Name: {refresh_data.get('document_name', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Country Issuing ID: {refresh_data.get('country_issuing_id', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"Refresh Status: {refresh_data.get('refresh_status', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"KYC Refresh Created Date: {refresh_data.get('onboarding_created_date', 'N/A')}").classes('text-lg text-gray-700')
                    with ui.row().classes('gap-4'):
                        ui.label(f"KYC Refresh Updated Date: {refresh_data.get('onboarding_updated_date', 'N/A')}").classes('text-lg text-gray-700')

ui.run(reload=False)