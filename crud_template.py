from pyairtable import Table
import csv
import os
import pandas as pd
import re
from dotenv import load_dotenv
import logging
import datetime
import streamlit as st


def crud(table, records):

    input_row_list = []
    inputRecords = records
    # Retrieve all existing records from the base through the Airtable REST API
    # If TABLE_VIEW is not set to a value, the script checks all records on the table.

    allExistingRecords = table.all()
    print('{} existing records found'.format(len(allExistingRecords)))

    # Create an object mapping of the primary field to the record ID
    # Remember, it's assumed that the AIRTABLE_UNIQUE_FIELD_NAME field is truly unique
    upsertFieldValueToExistingRecordId = {
        existingRecord['fields'].get('Roster Key'): existingRecord['id'] for existingRecord in
        allExistingRecords
    }

    # Create two arrays: one for records to be created, one for records to be updated
    recordsToCreate = []
    recordsToDelete = []
    # For each input record, check if it exists in the existing records. If it does, update it. If it does not, create it.
    st.info('Processing {} input records to determine whether to update or create. Please wait'.format(
        len(inputRecords)))
    for inputRecord in inputRecords:
        inputRecord['DateNo'] = str(inputRecord['DateNo'])
        recordUniqueValue = f'{inputRecord["Clinic"]}{inputRecord["DateNo"]}{inputRecord["Session"]}'

        existingRecordIdBasedOnUpsertFieldValueMaybe = upsertFieldValueToExistingRecordId.get(
            recordUniqueValue)

        # and if the upsert field value matches an existing one...
        if existingRecordIdBasedOnUpsertFieldValueMaybe:
            # Add record to list of records to update
            recordsToDelete.append(existingRecordIdBasedOnUpsertFieldValueMaybe)
            recordsToCreate.append(inputRecord)
                
        else:
            # Otherwise, add record to list of records to create
            # print('\t\tNo existing records match; adding to recordsToCreate')
            recordsToCreate.append(inputRecord)


    # Read out array sizes
    print("\n{} records to create".format(len(recordsToCreate)))
    print("{} records to update".format(len(recordsToDelete)))
    st.info("{} records to create.\n{} records to update. This will take quite a while".format(
        len(recordsToCreate), len(recordsToDelete) - len(recordsToCreate)))
    # Perform record delete on existing records
    table.batch_delete(recordsToDelete)
    # Perform record creation
    table.batch_create(recordsToCreate, typecast=True)

    


