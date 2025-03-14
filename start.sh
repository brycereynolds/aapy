#!/bin/bash

# Replace with your actual account ID
ACCOUNT_ID=""

# Create the output directory if it doesn't exist
mkdir -p books

# Run the script in interactive mode
python aapy.py interactive --account-id "$ACCOUNT_ID" --output books/

