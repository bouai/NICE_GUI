# 5. Getting data for screening
# print("\nStep 5: Invoking screening agent to scan the criminal records")
msg1 = "fill this json for client and member separately  {'Name': 'fill this data','Category': 'fill this data','Address': 'fill this data','Additional': 'fill this data in a string'} for screening"

SCREENING1 = f"""{msg1}"""

# 6. Check profile in screening data
# print("\nStep 6: Invoking screening agent to scan both client and member profiles.")
msg2 = (
    "Extract client and member names, check them in the screening tool, "
    "and return a clear, plain English summary of any matches. "
    "Avoid extra formatting, debug info, or XML. Only include relevant screening results."
)

SCREENING2 = f"""{msg2}"""

msg3 = "Extract individually client and member name and pass it in screening tool (person_info) to identify negative news."

SCREENING3 = f"""{msg3}"""