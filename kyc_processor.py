"""Modular functions for KYC processing."""

import json
import re
import datetime  # Add import for current date
import time  # Add import for retry delays
from typing import Any, Dict, List
import sqlite3  # Import sqlite3 for OperationalError

from agents import Runner
from utils.config import PRINT_RESPONSES
from prompts import analyst_prompt, researcher_prompt, screening_prompt
from utils.load import TimerContext
from tools.data_updater import insert_kyc_data

async def process_existing_data(agent, old_doc):
    """Step 1: Process existing client data."""
    with TimerContext("Step 1 - Process existing data"):
        print("Step 1: Invoking Researcher agent to read the existing data")
        result = await Runner.run(
            agent, 
            input=f"{researcher_prompt.RESEARCH1}<identifier>{old_doc}<identifier>")
        
        if PRINT_RESPONSES:
            print(f"\nResponse: {result.final_output}\n")
        return result

async def extract_new_data(agent, result, new_profile):
    """Step 2: Extract data from new profile."""
    with TimerContext("Step 2 - Extract new data"):
        print("\nStep 2: Invoking Researcher agent to extract the new data")
        result = await Runner.run(
            agent,
            input=result.to_input_list() + [
                {"content": f"{researcher_prompt.RESEARCH2}<new>{new_profile}<new>", "role": "user"}
            ],
        )
        return result

async def check_eligibility(agent, result):
    """Step 3: Check eligibility based on materiality rules."""
    with TimerContext("Step 3 - Check eligibility"):
        print("\nStep 3: Invoking Researcher agent to check the eligibility based on materiality rule")
        result = await Runner.run(
            agent,
            input=result.to_input_list() + [
                {"content": researcher_prompt.RESEARCH3, "role": "user"}
            ],
        )
        return result

async def update_profile(agent, result):
    """Step 4: Create update query for KYC database."""
    with TimerContext("Step 4 - Update profile"):
        print("\nStep 4: Invoking Analyst agent to validate and update the data in KYC database")
        result = await Runner.run(
            agent,
            input=result.to_input_list() + [
                {"content": analyst_prompt.ANALYST, "role": "user"}
            ],
        )
        
        if PRINT_RESPONSES:
            print(f"\nResponse: {result.final_output}\n")
        
        # Clean and extract JSON from response
        try:
            # Strip and clean the output
            output = result.final_output.strip()
            
            # Remove markdown code block indicators if present
            output = re.sub(r'^```(json)?|```$', '', output, flags=re.MULTILINE)
            
            # Find JSON object
            json_match = re.search(r'(\{[\s\S]*\})', output)
            if json_match:
                output = json_match.group(1)
            
            # Parse JSON
            update_data = json.loads(output)
            
            # Store for later use
            result.update_data = update_data
            
            # Extract client_identifier and update_dict
            client_identifier = update_data.get('client_identifier')
            update_dict = update_data.get('update_dict')
            
            if client_identifier and update_dict:
                # Add current date for date columns if not provided
                current_date = datetime.date.today().strftime('%Y-%m-%d')
                date_columns = [
                    'date_of_birth', 'KycRefresh_created_date',
                    'KycRefresh_updated_date'
                ]
                for col in date_columns:
                    if col not in update_dict or not update_dict[col]:
                        update_dict[col] = current_date

                # Update or insert data
                retries = 5
                for attempt in range(retries):
                    try:
                        # Update or insert data
                        rows_affected = insert_kyc_data(client_identifier, update_dict)
                        print(f"Inserted data for client {client_identifier}, rows affected: {rows_affected}")
                        break
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e) and attempt < retries - 1:
                            print(f"Database is locked. Retrying in 1 second... (Attempt {attempt + 1}/{retries})")
                            time.sleep(1)
                        else:
                            raise
            else:
                print("Warning: Missing client_identifier or update_dict in JSON response")
                
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON from analyst agent response: {e}")
            print(f"Raw output: {result.final_output}")
            result.update_data = None
        except Exception as e:
            print(f"Warning: Error processing analyst agent response: {e}")
            result.update_data = None
            
        return result

async def scan_criminal_records(agent, result):
    """Step 5: Scan criminal records."""
    with TimerContext("Step 5 - Scan criminal records"):
        print("\nStep 5: Invoking screening agent to scan the criminal records")
        result = await Runner.run(
            agent,
            input=result.to_input_list() + [
                {"content": screening_prompt.SCREENING1, "role": "user"}
            ],
        )
        return result

async def scan_profiles(agent, result):
    """Step 6: Scan client and member profiles."""
    with TimerContext("Step 6 - Scan profiles"):
        print("\nStep 6: Invoking screening agent to scan both client and member profiles.")
        result = await Runner.run(
            agent,
            input=result.to_input_list() + [
                {"content": screening_prompt.SCREENING2, "role": "user"}
            ],
        )
        return result
    
async def adverse_media(agent, result):
    """Step 7: Scan client and member profiles."""
    with TimerContext("Step 6 - Scan profiles"):
        print("\nStep 7: Invoking screening agent to perform adverse media search")
        result = await Runner.run(
            agent,
            input=result.to_input_list() + [
                {"content": screening_prompt.SCREENING3, "role": "user"}
            ],
        )
        return result

async def generate_final_report(agent, result, client_identifier):
    """Step 8: Generate the final report and update the database."""
    with TimerContext("Step 8 - Generate final report"):
        print("\nStep 8: Final Result")
        summary_request = {
            "content": """fill this result in <result> tag in json format. Return ONLY a JSON object with these keys:
1. No. of material changes,
2. No. of non material changes,
3. Researcher agent used - 1 for yes and 0 for no,
4. Outreach agent required - 1 if information is incomplete and outreach agent required and 0 for no,
5. Analyst agent invoked - 1 if data updated in database and 0 for no,
6. Screening hit - 1 for yes and 0 for no,
7. Adverse Media Search - Person name with identified negative profile

Example:
{
    "No. of material changes": 2,
    "No. of non material changes": 1,
    "Researcher agent used": 1,
    "Outreach agent required": 0,
    "Analyst agent invoked": 1,
    "Screening hit": 0,
    "Adverse Media Search": "John Doe"
}
Return ONLY the JSON object, no explanations.""",
            "role": "user"
        }
        
        result = await Runner.run(
            agent,
            input=result.to_input_list() + [summary_request],
        )
        print(f"\nResponse: {result.final_output}\n")

        # Parse the result and update the database
        try:
            # Extract JSON from the agent's response
            output = result.final_output.strip()
            output = re.sub(r'^```(json)?|```$', '', output, flags=re.MULTILINE)  # Remove markdown code block indicators
            json_match = re.search(r'(\{[\s\S]*\})', output)
            if json_match:
                output = json_match.group(1)
            summary_data = json.loads(output)

            # Extract fields to update
            screening_agent_status = summary_data.get("screening_hit", 0)
            outreach_agent_status = summary_data.get("outreach_agent_required", 0)
            research_agent_status = summary_data.get("Researcher agent used", 0)
            analyst_agent_status = summary_data.get("analyst agent invoked", 0)
            refresh_status = 1 if analyst_agent_status == 1 else 0
            material_changename = f"{summary_data.get('No. of material changes', 0)} material changes"

            # Update the database
            conn = sqlite3.connect("data/KYC_Database.db")
            try:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE KycRefreshData
                    SET screening_agent_status = ?,
                        outreach_agent_status = ?,
                        research_agent_status = ?,
                        analyst_agent_status = ?,
                        refresh_status = ?,
                        material_changename = ?
                    WHERE client_identifier = ?
                """, (
                    screening_agent_status,
                    outreach_agent_status,
                    research_agent_status,
                    analyst_agent_status,
                    refresh_status,
                    material_changename,
                    client_identifier
                ))
                conn.commit()
                print(f"Updated KycRefreshData for client_identifier={client_identifier}")
            finally:
                conn.close()
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON from final report response: {e}")
            print(f"Raw output: {result.final_output}")
        except Exception as e:
            print(f"Error updating KycRefreshData: {e}")

        return result
