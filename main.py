"""Main entry point for the KYC processing system."""

import time
import asyncio
import json
import sqlite3  # Add import for database interaction
from tools.data_validator import validator
from tools.data_fuzzy_match import fuzzy_tool, person_info
from tools.data_extractor import information_extractor
from agents_call.orchestration_agent import run_interaction_agent
from agent_evaluation import AgentEvaluation, evaluate_agent_steps
from tools.data_updater import fetch_kyc_data, insert_kyc_data
# Import modular components
from utils.config import CLIENT_ID, EXTRACTED_DATA_PATH, DB_PATH
from utils import load
from utils.kyc_processor import (
    process_existing_data,
    extract_new_data,
    check_eligibility,
    update_profile,
    scan_criminal_records,
    scan_profiles,
    adverse_media,
    generate_final_report,
)

import warnings
warnings.filterwarnings('ignore')


def initialize_agent():
    """Initialize the orchestration agent with required tools."""
    return run_interaction_agent(information_extractor, validator, fuzzy_tool, person_info)

async def run_kyc_workflow():
    """Run the complete KYC workflow."""
    # Initialize agent
    orchestrator_agent = initialize_agent()
    
    # Fetch NEW_DOC dynamically from the database
    client_identifier = CLIENT_ID
    NEW_DOC = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT extracted_data FROM OnboardingData WHERE client_identifier = ?",
            (client_identifier,)
        )
        result = cursor.fetchone()
        if result:
            NEW_DOC = result[0]
        else:
            raise ValueError(f"No extracted_data found for client_identifier: {client_identifier}")
    except Exception as e:
        print(f"Error fetching NEW_DOC from database: {e}")
        return
    finally:
        conn.close()

    # Load the new profile data
    profile = load.load_document(f"{EXTRACTED_DATA_PATH}{NEW_DOC}")
    # print(f"Loaded new profile data: {profile}")
    # Start the workflow timer
    t0 = time.time()
    
    print("\n=== Event driven KYC Review process : Intelligent Automation using AI agents ===\n")
    
    # Agent evaluation setup
    step_names = [
        "Profile Identification (Researcher Agent)",
        "Extract New Data (Researcher Agent)",
        "Check Eligibility (Researcher Agent)",
        "Profile Update (Analyst Agent)",
        "Scan Criminal Records (Screening Agent)",
        "Scan Profiles (Screening Agent)",
        "Adverse Media (Screening Agent)",
        "Final Report (Orchestrator Agent)"
    ]
    eval_steps = evaluate_agent_steps(step_names)
    agent_eval = AgentEvaluation(client_identifier)

    # Execute each step of the KYC process
    try:
        eval_steps[0].start()
        result1 = await process_existing_data(orchestrator_agent, client_identifier)
        print("Result of process_existing_data:", result1)
        eval_steps[0].end(result=getattr(result1, "final_output", str(result1)))
        agent_eval.add_step(eval_steps[0])

        eval_steps[1].start()
        result2 = await extract_new_data(orchestrator_agent, result1, profile)
        print("Result of extract_new_data:", result2)
        eval_steps[1].end(result=getattr(result2, "final_output", str(result2)), reference=profile)
        agent_eval.add_step(eval_steps[1])

        eval_steps[2].start()
        result3 = await check_eligibility(orchestrator_agent, result2)
        print("Result of check_eligibility:", result3)
        eval_steps[2].end(result=getattr(result3, "final_output", str(result3)), reference=profile)
        agent_eval.add_step(eval_steps[2])

        eval_steps[3].start()
        result4 = await update_profile(orchestrator_agent, result3)
        print("Result of update_profile:", result4)
        eval_steps[3].end(result=getattr(result4, "final_output", str(result4)), reference=profile)
        agent_eval.add_step(eval_steps[3])

        # --- NEW: Parse update data from agent and update DB ---
        # Try to extract update_info from result in various formats
        update_info = getattr(result4, "update_data", None)
        if not update_info:
            # Try to parse from final_output if present
            final_output = getattr(result4, "final_output", None)
            if final_output:
                try:
                    # Try to load as JSON (could be dict or list)
                    parsed = json.loads(final_output)
                    update_info = parsed
                except Exception:
                    # Try to extract JSON from string if agent returned a string with JSON inside
                    import re
                    match = re.search(r'(\{.*"update_dict".*\})', final_output, re.DOTALL)
                    if match:
                        try:
                            update_info = json.loads(match.group(1))
                        except Exception:
                            update_info = None

        # If update_info is a list, process each item
        if isinstance(update_info, list):
            for info in update_info:
                client_id = info.get("client_identifier")
                update_dict = info.get("update_dict")
                if client_id and update_dict:
                    # Use insert_kyc_data instead of update_kyc_data
                    # updated_rows = insert_kyc_data(client_id, update_dict)
                    # print(f"Database row inserted for client_identifier={client_id}, rows affected: {updated_rows}")
                    updated_row = fetch_kyc_data(client_id)
                    # print("Inserted data:", updated_row)
                    agent_eval.set_updated_data(updated_row)
                else:
                    print("Warning: update_info missing client_identifier or update_dict.")
        elif isinstance(update_info, dict):
            client_id = update_info.get("client_identifier")
            update_dict = update_info.get("update_dict")
            if client_id and update_dict:
                # Use insert_kyc_data instead of update_kyc_data
                # updated_rows = insert_kyc_data(client_id, update_dict)
                # print(f"Database row inserted for client_identifier={client_id}, rows affected: {updated_rows}")
                updated_row = fetch_kyc_data(client_id)
                # print("Inserted data:", updated_row)
                agent_eval.set_updated_data(updated_row)
            else:
                print("Warning: update_info missing client_identifier or update_dict.")
        else:
            print("Warning: No update_info returned from agent. Skipping DB update.")

        eval_steps[4].start()
        result5 = await scan_criminal_records(orchestrator_agent, result4)
        print("Result of scan_criminal_records:", result5)
        eval_steps[4].end(result=getattr(result5, "final_output", str(result5)), reference=profile)
        agent_eval.add_step(eval_steps[4])

        eval_steps[5].start()
        result6 = await scan_profiles(orchestrator_agent, result5)
        print("Result of scan_profiles:", result6)
        eval_steps[5].end(result=getattr(result6, "final_output", str(result6)), reference=profile)
        agent_eval.add_step(eval_steps[5])

        eval_steps[6].start()
        result7 = await adverse_media(orchestrator_agent, result6)
        print("Result of scan_profiles:", result7)
        eval_steps[6].end(result=getattr(result7, "final_output", str(result7)), reference=profile)
        agent_eval.add_step(eval_steps[5])

        eval_steps[7].start()
        result8 = await generate_final_report(orchestrator_agent, result7, client_identifier)
        final_output = getattr(result8, "final_output", None)

        # Try to parse the result if it's a dict with a 'content' key
        if isinstance(final_output, dict) and "content" in final_output:
            # Try to extract JSON from the content string
            import re, json
            match = re.search(r'\{.*\}', final_output["content"], re.DOTALL)
            if match:
                try:
                    parsed_result = json.loads(match.group(0))
                    # Use parsed_result as your result
                except Exception:
                    print("Could not parse JSON from agent content.")
            else:
                print("No JSON found in agent content.")
        elif isinstance(final_output, dict):
            # Handle as usual
            pass
        else:
            # Handle as string or other type
            pass

        eval_steps[7].end(result=getattr(result8, "final_output", str(result8)), reference=profile)
        agent_eval.add_step(eval_steps[6])

    except Exception as e:
        # Mark the current step as failed
        for step in eval_steps:
            if step.status == "running":
                step.end(error=e)
                agent_eval.add_step(step)
                break
        print(f"Error during KYC workflow: {e}")

    # Calculate total time
    total_time = time.time() - t0
    print(f"\nTotal processing time: {int(total_time)} sec")
    print("\n=== Demo Complete ===\n")

    # Generate agent evaluation report
    agent_eval.report()

if __name__ == "__main__":
    asyncio.run(run_kyc_workflow())