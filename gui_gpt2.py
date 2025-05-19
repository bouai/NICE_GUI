from nicegui import ui
import sqlite3
import pandas as pd

DB_PATH = 'Data/KYC_DataBase.db'
TABLE_NAME_1 = 'OnboardingData'
TABLE_NAME_2 = 'KycRefreshData'
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
    """Fetch and merge onboarding and refresh data."""
    with sqlite3.connect(DB_PATH) as conn:
        onboard = pd.read_sql_query(
            f"""
            SELECT
                id,
                entity_legal_name,
                client_identifier,
                document_name
            FROM {TABLE_NAME_1}
            """, conn)
        refresh = pd.read_sql_query(
            f"""
            SELECT
                client_identifier,
                material_change,
                refresh_status,
                KycRefresh_created_date,
                KycRefresh_created_date AS sla_start_date,
                KycRefresh_updated_date
            FROM {TABLE_NAME_2}
            """, conn)
    df = pd.merge(onboard, refresh, on='client_identifier', how='left')
    # ensure strings
    for col in ['entity_legal_name', 'material_change', 'refresh_status','document_name']:
        if col in df.columns:
            df[col] = df[col].astype(str)
    # SLA on onboarding
    df['KycRefresh_created_date'] = pd.to_datetime(df['KycRefresh_created_date'], errors='coerce')
    df['sla_start_date'] = pd.to_datetime(df['sla_start_date'], errors='coerce')
    df['case_sla_date'] = df['sla_start_date'] + pd.Timedelta(days=90)
    df['KycRefresh_updated_date'] = pd.to_datetime(df['KycRefresh_updated_date'], errors='coerce')
    
    # format dates as YYYY‑MM‑DD, and fill any NaT with "N/A"
    for col in ['KycRefresh_created_date', 'case_sla_date', 'KycRefresh_updated_date']:
        df[col] = df[col].dt.strftime('%Y-%m-%d').fillna('N/A')
    
    return df

def filter_df(df, name, material, status, case_id, data_source):
    if name:
        df = df[df['entity_legal_name'].str.contains(name, case=False, na=False)]
    if material:
        df = df[df['material_change'].str.contains(material, case=False, na=False)]
    if status:
        df = df[df['refresh_status'].str.contains(status, case=False, na=False)]
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
                
                # Update to handle material_change field
                material_change_value = row.get('material_change', None)
                if pd.isna(material_change_value) or material_change_value is None or str(material_change_value).strip() == '' or material_change_value == 'nan':
                    material_change_display = "No"
                else:
                    material_change_display = "Yes" if material_change_value and material_change_value != '0' else "No"
                ui.label(material_change_display).classes('w-40 text-center text-gray-700')
                
                # Replace refresh_status label with a button
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
                ui.label(row.get('document_name', '')).classes('w-40 text-center text-gray-700')
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

def dashboard_page():
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
            filter_inputs['status'] = ui.input('Refresh Status', value=dashboard_state['status']).props('clearable outlined dense').classes('w-56 bg-gray-50')
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
            for col in ['Client Name', 'Material Change', 'Refresh Status', 'Case ID', 'Data Source', 'KYC Creation Date', 'Case SLA Date', 'KYC Updated Date']:
                ui.label(col).classes('w-40 text-center')  # Ensure consistent width for all columns
        
        data_table = ui.column()

    for _, row in paginated.iterrows():
        with data_table:
            with ui.row().classes('border-b p-3 items-center hover:bg-gray-50 transition-all rounded-lg'):
                ui.link(row['entity_legal_name'], f'/client/{row["id"]}').classes('text-blue-600 font-medium underline w-40 text-center')
                
                # Update to handle material_change field
                material_change_value = row.get('material_change', None)
                if pd.isna(material_change_value) or material_change_value is None or str(material_change_value).strip() == '' or material_change_value == 'nan':
                    material_change_display = "No"
                else:
                    material_change_display = "Yes" if material_change_value and material_change_value != '0' else "No"
                ui.label(material_change_display).classes('w-40 text-center text-gray-700')
                
                # Replace refresh_status label with a button
                refresh_status_value = get_refresh_status(row['client_identifier'])
                if refresh_status_value == '1':
                    refresh_status_display = "KYC Refresh is triggered"
                    button_classes = 'w-40 text-center bg-blue-500 text-white hover:bg-blue-600'
                elif refresh_status_value == '0':
                    refresh_status_display = "Profile Updates Absorbed"
                    button_classes = 'w-40 text-center bg-green-500 text-white hover:bg-green-600'
                else:
                    refresh_status_display = "KYC Not Triggered"
                    button_classes = 'w-40 text-center bg-gray-400 text-white hover:bg-gray-500'

                ui.button(
                    refresh_status_display,
                    on_click=lambda client_id=row['id']: ui.navigate.to(f'/client/{client_id}')
                ).classes(button_classes)

                ui.label(row.get('client_identifier', '')).classes('w-40 text-center text-gray-700')
                ui.label(row.get('document_name', '')).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('KycRefresh_created_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('case_sla_date', ''))[:10]).classes('w-40 text-center text-gray-700')
                ui.label(str(row.get('KycRefresh_updated_date', ''))[:10]).classes('w-40 text-center text-gray-700')

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

def get_refresh_status(client_identifier):
    """Fetch the latest refresh_status from KycRefreshData for a given client_identifier."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT refresh_status FROM KycRefreshData WHERE client_identifier = ?", (client_identifier,))
        result = cur.fetchone()
        return str(result[0]) if result else ''

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
            'material_change': 'N/A',
            'KycRefresh_created_date': 'N/A',
            'KycRefresh_updated_date': 'N/A',
        }
    else:
        refresh_data = refresh_df.iloc[0].to_dict()

    # Use dummy values for Screening Data
    # In a real application, this data would be fetched from the database
    # use these variable to capture data from DB.
    screening_data = {
        'screening_agent_status': 'Sam Bankman Freid, Osama bin Laden, John Doe',
        'adverse_media_result': '0',
    }

    # dummy values for Agent Performance
    # In a real application, this data would be fetched from the database
    # use these variable to capture data from DB.
    agent_data = {
        'researcher_time': '2h',
        'researcher_accuracy': '95%',
        'researcher_tool_called': 'Yes',
        'kyc_analyst_time': '3h',
        'kyc_analyst_accuracy': '90%',
        'kyc_analyst_tool_called': 'No',
        'screening_time': '1h',
        'screening_accuracy': '98%',
        'screening_tool_called': 'Yes',
    }

    # Page layout with enhanced styling
    with ui.element('div').classes('bg-gradient-to-r from-blue-600 to-blue-800 text-white p-8 rounded-xl shadow-2xl mb-8 w-full'):
        # Display the client name dynamically
        ui.label(onboarding_data['entity_legal_name']).classes('text-4xl font-bold text-center tracking-tight')
        ui.label('KYC Review Process: Intelligent Automation Using AI Agents').classes('text-xl text-center mt-2 opacity-90')

    with ui.element('div').classes('container mx-auto px-4'):
        # First Row: Onboarding and KYC Refresh Details
        ui.label('Client KYC Details').classes('text-2xl font-semibold text-blue-600 mb-4')  # Title for the first row
        with ui.element('div').classes('grid grid-cols-1 md:grid-cols-2 gap-6 mb-8'):
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Existing Details').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.column().classes('gap-1'):
                    ui.label(f"Client Name: {onboarding_data['entity_legal_name']}").classes('text-lg text-gray-600 font-medium')
                    ui.label(f"Client Identifier: {onboarding_data.get('client_identifier', 'N/A')}").classes('text-lg text-gray-600')
                    ui.label(f"Client Type: {onboarding_data.get('member_type', 'N/A')}").classes('text-lg text-gray-600')
                    ui.label(f"Client Domicile Country: {onboarding_data.get('country_issuing_id', 'N/A')}").classes('text-lg text-gray-600')
                    ui.label(f"Client Documents: {onboarding_data.get('document_name', 'N/A')}").classes('text-lg text-gray-600')

            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Refresh Details').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.row().classes('gap-2'):  # Create a row to split content into two sections
                    # Left Section
                        with ui.column().classes('gap-1 w-5/9'):  # Left section takes half the width
                            ui.label(f"Client Name: {refresh_data.get('entity_legal_name', 'N/A')}").classes('text-lg text-gray-600 font-medium')
                            ui.label(f"Client Identifier: {refresh_data.get('client_identifier', 'N/A')}").classes('text-lg text-gray-600')
                            ui.label(f"Client Type: {refresh_data.get('member_type', 'N/A')}").classes('text-lg text-gray-600')
                            ui.label(f"Client Domicile Country: {refresh_data.get('country_issuing_id', 'N/A')}").classes('text-lg text-gray-600')
                            ui.label(f"Client Documents: {refresh_data.get('document_name', 'N/A')}").classes('text-lg text-gray-600')
                            

                    # Right Section (Separate UI Card)
                        with ui.column().classes('gap-3 pl-4 w-4/9'): 
                            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300'):
                                refresh_status_value = str(refresh_data.get('refresh_status', ''))
                                #ui.label(f"Refresh Status: {refresh_status_value}").classes('text-lg text-gray-600 font-medium')
                                ui.label(f"Refresh Created Date: {refresh_data.get('KycRefresh_created_date', 'N/A')}").classes('text-lg text-gray-600')
                                ui.label(f"Refresh Updated Date: {refresh_data.get('KycRefresh_updated_date', 'N/A')}").classes('text-lg text-gray-600')

                                 # Add the status button here
                                if refresh_status_value == '1':
                                    ui.button(
                                        "KYC Refresh is Triggered"
                                    ).classes('w-56 text-center bg-blue-500 text-white rounded-md hover:bg-blue-600 mt-2')
                                elif refresh_status_value == '0':
                                    ui.button(
                                        "Profile Updates Absorbed"
                                    ).classes('w-56 text-center bg-green-500 text-white rounded-md hover:bg-green-600 mt-2')
                                else:  # Covers both '' and None
                                    ui.button(
                                        "KYC Refresh Not Triggered"
                                    ).classes('w-56 text-center bg-green-500 text-white rounded-md hover:bg-green-600 mt-2')
                                                
        # Second Row: Materiality, Screening, Agents Performance
        ui.label('Additional Details').classes('text-2xl font-semibold text-blue-600 mb-4')  # Title for the second row
        with ui.element('div').classes('grid grid-cols-1 lg:grid-cols-3 gap-6'):
            # Materiality Card
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Researcher Agent').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.column().classes('gap-3'):
                    # 1. Materiality Hit logic
                    material_change_val = refresh_data.get('material_change', '')
                    if material_change_val and str(material_change_val).strip() != '' and str(material_change_val).strip() != '0':
                        materiality_hit = "Yes"
                    else:
                        materiality_hit = "No"
                    ui.label(f"Materiality Hit: {materiality_hit}").classes('text-lg text-gray-600 font-medium')

                    with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 mt-4 w-full'):
                        ui.label('Material Changes:').classes('text-lg font-semibold text-gray-600')
                        with ui.column().classes('gap-2 pl-10'):
                            for _, row in refresh_df.iterrows():
                                mat_val = row.get('material_change', '')
                                # Show string if present and not '0', else show N/A
                                if mat_val and str(mat_val).strip() != '' and str(mat_val).strip() != '0':
                                    mat_val_display = str(mat_val)
                                else:
                                    mat_val_display = 'N/A'
                                ui.label(f"Material Change: {mat_val_display}").classes('text-sm text-gray-500')

                    # Conditional UI card based on Materiality Hit
                    if refresh_data.get('material_change', 'NO') == 'YES':
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
                ui.label('Screening').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200 ')
                with ui.column().classes('gap-3'):

                    # Extract and normalize the status
                    opac_status_raw = screening_data.get('screening_agent_status', '')
                    search_status_raw = screening_data.get('adverse_media_result', '')
                    screening_status = str(opac_status_raw).strip() if opac_status_raw is not None else ''
                    adverse_search_status = str(search_status_raw).strip() if search_status_raw is not None else ''
                    # Determine display values
                    opac_hit = 'YES' if screening_status and screening_status != '0' else 'NO'
                    hit_details = screening_status if screening_status and screening_status != '0' else 'N/A'
                    search_details = adverse_search_status if adverse_search_status and adverse_search_status != '0' else 'No Hit Detected'
                    # OPAC Hit Card
                    with ui.row().classes('justify-center mt-4'):
                        with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 mt-4 w-full'):
                            ui.label(f"OPAC Hit: {opac_hit}").classes('text-lg font-semibold text-gray-600 justify-center items-center')
                            ui.label(f"Hit Details: {hit_details}")
                    # Adverse Media Search Card
                    with ui.row().classes('justify-center items-center mt-4 w-full'):
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 mt-4 w-full'):
                            ui.label('Adverse Media Search').classes('text-lg font-semibold text-gray-600 justify-center items-center')
                            ui.label(f"Hit Details: {search_details}")

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
            with ui.card().classes('p-6 bg-white rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow duration-300'):
                ui.label('Agent Logs').classes('text-2xl font-semibold text-gray-800 mb-4 border-b pb-2 border-gray-200')
                with ui.column().classes('gap-3'):
                    with ui.row().classes('justify-center items-center mt-4 w-full'):
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 w-full'):
                            ui.label('Researcher Agent     |     Total Jobs: 3').classes('text-lg font-semibold text-gray-600')
                            with ui.column().classes('gap-1 pl-4'):    
                                ui.label(f"Time Taken: {agent_data.get('researcher_time', 'N/A')}")
                                ui.label(f"Tool Called: {agent_data.get('researcher_tool_called', 'NO')}")
                                ui.label(f"Precision: {agent_data.get('researcher_accuracy', 'N/A')}")
        
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 w-full'):
                            ui.label('KYC Analyst Agent     |     Total Jobs: 1').classes('text-lg font-semibold text-gray-600 mt-2')
                            with ui.column().classes('gap-1 pl-4'):
                                ui.label(f"Time Taken: {agent_data.get('kyc_analyst_time', 'N/A')}")
                                ui.label(f"Tool Called: {agent_data.get('kyc_analyst_tool_called', 'NO')}")
                                ui.label(f"Record Insertion Accuracy: {agent_data.get('kyc_analyst_accuracy', 'N/A')}")
                                
                        with ui.card().classes('pl-5 p-6 bg-white rounded-xl shadow-lg border border-blue-500 hover:shadow-xl transition-shadow duration-300 w-full'): 
                            ui.label('Screening Agent     |     Total Jobs: 2').classes('text-lg font-semibold text-gray-600 mt-2')
                            with ui.column().classes('gap-1 pl-4'):
                                ui.label(f"Time Taken: {agent_data.get('screening_time', 'N/A')}")
                                ui.label(f"Tool Called: {agent_data.get('screening_tool_called', 'NO')}")
                                ui.label(f"Hit Detection precision: {agent_data.get('screening_accuracy', 'N/A')}")
       

ui.run(reload=False)