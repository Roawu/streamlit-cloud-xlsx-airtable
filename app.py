from streamlit.runtime.scriptrunner.script_run_context import add_script_run_ctx
from threading import current_thread
from contextlib import contextmanager
from io import StringIO
import sys
import logging
import time
import pandas as pd
from dateutil.parser import parse
from dotenv import load_dotenv
import os
from pyairtable import Table
import datetime
import streamlit as st

from utils import (
    get_dr_reference,
    get_people_reference,
    get_da_reference,
    get_dr_roster,
    process_dr_schedule,
    process_ahq_schedule,
    get_location_index,
    dr_abb_validation,
    da_abb_validation,
    check_roster_title_format,
    get_appointment_color,
)

from crud_template import crud

st.set_page_config(page_title="Roster Upload", layout="wide")


@contextmanager
def st_redirect(src, dst):
    placeholder = st.empty()
    output_func = getattr(placeholder, dst)

    with StringIO() as buffer:
        old_write = src.write

        def new_write(b):
            if getattr(current_thread(), add_script_run_ctx().name, None):
                buffer.write(b + "")
                output_func(buffer.getvalue() + "")
            else:
                old_write(b)

        try:
            src.write = new_write
            yield
        finally:
            src.write = old_write


@contextmanager
def st_stdout(dst):
    "this will show the prints"
    with st_redirect(sys.stdout, dst):
        yield


@contextmanager
def st_stderr(dst):
    "This will show the logging"
    with st_redirect(sys.stderr, dst):
        yield


# cache dr roster
@st.cache
def extract_dr_roster(uploaded_file):
    return get_dr_roster(uploaded_file)


# transform doctor roster fuction
def transform_dr_roster(uploaded_file):
    # extract doctor roster from file
    roster = extract_dr_roster(uploaded_file)

    roster_date = roster.loc[1, 4:]
    # get clinic location index
    location_index_dict = get_location_index(roster)
    print(location_index_dict)

    output_list = []
    for l in location_index_dict.keys():
        if l == "AHQ":
            l_index = location_index_dict[l]
            da_am = roster.loc[l_index, 4:]
            da_pm = roster.loc[l_index + 1, 4:]
            da_night = roster.loc[l_index + 2, 4:]
            am_output = process_ahq_schedule(da_am, roster_date, l, "AM")
            # process PM schedule
            pm_output = process_ahq_schedule(da_pm, roster_date, l, "PM")
            # process night schedule
            night_output = process_ahq_schedule(da_night, roster_date, l, "NIGHT")

        else:
            l_index = location_index_dict[l]
            am = roster.loc[l_index, 4:]
            da_am = roster.loc[l_index + 3, 4:]
            pm = roster.loc[l_index + 1, 4:]
            da_pm = roster.loc[l_index + 4, 4:]
            night = roster.loc[l_index + 2, 4:]
            da_night = roster.loc[l_index + 5, 4:]
            am_output = process_dr_schedule(am, da_am, roster_date, l, "AM")
            # process PM schedule
            pm_output = process_dr_schedule(pm, da_pm, roster_date, l, "PM")
            # process night schedule
            night_output = process_dr_schedule(night, da_night, roster_date, l, "NIGHT")

        # process AM schedule

        output_list += am_output + pm_output + night_output
        # print(output_list)

    clean_roster = pd.DataFrame(output_list)

    return clean_roster


# cache dr reference
@st.cache
def extract_dr_reference(uploaded_file):
    return get_dr_reference(uploaded_file)


@st.cache
def extract_da_reference(uploaded_file):
    return get_da_reference(uploaded_file)


# get environment key
load_dotenv()
roster_airtable_api_key = os.getenv('ROSTER_AIRTABLE_API_KEY')
roster_base_id = os.getenv('ROSTER_BASE_ID')
roster_table_id = os.getenv('ROSTER_TABLE_ID')
roster_people_id = os.getenv('ROSTER_PEOPLE_TABLE_ID')
roster_clinic_id = os.getenv('ROSTER_CLINIC_TABLE_ID')
password = os.getenv("PASSWORD")
crud_list = []
clinics_list = []

database_dict = {
    0: {'label': 'Airtable Roster Master', 'key': roster_airtable_api_key},
}

roster_type_dict = {
    'Confirmed': '',
    'Tentative': 'LPm5'
}


def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.header("Input correct password to access")
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        if not st.session_state["show_upload"]:
            st.header("Input correct password to access")
            # Password not correct, show input + error.
            st.text_input(
                "Password", type="password", on_change=password_entered, key="password"
            )
            st.error("😕 Password incorrect")
            return False
    else:
        # Password correct.
        return True


if __name__ == "__main__":
    if check_password():
        st.header('Upload')

        database_options = list(range(len(database_dict)))
        selected_database_index = st.selectbox(
            "Select Database", database_options, format_func=lambda x: database_dict[x]['label'])

        uploaded_file = False

        # if api key is not provided, print error
        if roster_airtable_api_key == None:
            st.error("Please provide AIRTABLE_API_KEY")
        else:
            # upload file button
            zTable = Table(roster_airtable_api_key, roster_base_id, roster_table_id)
            pTable = Table(roster_airtable_api_key, roster_base_id, roster_people_id)
            cTable = Table(roster_airtable_api_key, roster_base_id, roster_clinic_id)
            uploaded_file = st.file_uploader(
                "Choose doctor roster XLSX file", type="xlsx")

        if uploaded_file:
            # if file is uploaded, transform doctor roster into dataframe
            clean_roster = transform_dr_roster(uploaded_file)
            st.dataframe(clean_roster)
            if 'show_upload' not in st.session_state:
                st.session_state['show_upload'] = False
            validate_button = st.button("Validate")
            if validate_button:
                for i in pTable.all(fields="Initials"):
                    clinics_list.append(i["fields"]["Initials"])
                # if validate button is pressed, extract doctor reference and validate with ABB sheet
                d2_ref_df = get_people_reference(pTable)
                error_list = dr_abb_validation(clean_roster, d2_ref_df)
                error2_list = da_abb_validation(clean_roster, d2_ref_df)

                if error_list is not None:
                    for e in error_list:
                        st.error(
                            "Doctor error record: clinic {}, timeslot {}, date {}, name {} da {}".format(
                                e["clinic"], e["time_slot"], e["date"], e["staff"], e["DAs"]
                            )
                        )
                    st.session_state['show_upload'] = False
                else:
                    if error2_list is not None:
                        for e in error2_list:
                            st.error(
                                "DA error record: clinic {}, timeslot {}, date {}, name {} da {}".format(
                                    e["clinic"], e["time_slot"], e["date"], e["staff"], e["DAs"]
                                )
                            )
                        st.session_state['show_upload'] = False
                    else:
                        st.session_state['show_upload'] = True
                        st.info("Validated, all the doctor and DA codes match the reference.")

            if st.session_state['show_upload']:
                selected_clinic_upload = st.multiselect(
                    'Select clinic',
                    ['ALL'] + clinics_list, ['ALL'], key=123)

                if 'ALL' in selected_clinic_upload:
                    filtered_roster = clean_roster
                else:
                    filtered_roster = clean_roster[clean_roster['clinic'].isin(
                        selected_clinic_upload)]
                st.dataframe(filtered_roster)

                upload_button = st.button("Upload")
                if upload_button:
                    with st_stdout("success"), st_stderr("code"):
                        logging.info("Total doctor schedule: {}".format(
                            filtered_roster.shape[0]))
                        for i, row in filtered_roster.iterrows():
                            if row['clinic']:
                                row["staff"] = row["staff"].replace(" ", ", ")
                                row["DAs"] = str(row["DAs"])
                                row["DAs"] = row["DAs"].replace(" ", ", ")
                                for ch in ['(', ')', 'nan']:
                                    if ch in row["DAs"]:
                                        row["DAs"] = row["DAs"].replace(ch, "")
                                try:
                                    row["date"] = datetime.datetime.strptime(row["date"], "%Y-%m-%d %H:%M:%S")
                                except:
                                    pass
                                row["date"] = (row["date"] - datetime.datetime(1900, 1, 1)).days + 2
                                record = {
                                    'Doctors': row["staff"],
                                    'DAs': row["DAs"],
                                    'DateNo': row["date"],
                                    'Session': row["time_slot"],
                                    'Clinic': row["clinic"]
                                }
                                crud_list.append(record)
                            else:
                                logging.info(
                                    "Clinic {} is not in the mapping list, skip creating schedule".format(
                                        row['clinic']))
                        st.info('Reading Airtable Roster to upsert data')
                        crud(zTable, crud_list)

                        logging.info("Done creating schedules in Airtable")
                        st.info("Done creating schedules in Airtable")
                        st.session_state['show_upload'] = False




