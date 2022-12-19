import pandas as pd
import re
from pyairtable import Table

# clinic code maps

# clinic room maps

# get appointment by location and room
def get_appointment_color(location, room):
    location = clinic_maps.get(location)

    if location is None:
        return None

    color = clinic_room_maps.get(str(location) + str(room))
    if color is None:
        color = 'RM{}{}'.format(room, location)
    
    return color

# process dr schedule
def process_dr_schedule(schedule, daschedule, roster_date, location, shift):
    output = []
    for s, d, date in zip(schedule.values, daschedule.values, roster_date):
        if isinstance(s, int):
            s = ""
        if isinstance(s, float):
            s = ""
        if s == "-":
            s = ""
        if d == 0:
            d = ""
        print(date)
        print(type(date))
        if date == "00:00:00":
            continue           
        # room = 1
        output.append(
            {
                "clinic": location,
                "time_slot": shift,
                "date": date,
                "staff": s,
                "DAs": d,
                # "room": room,
            }
        )
        # room += 1
    return output
def process_ahq_schedule(daschedule, roster_date, location, shift):
    output = []
    for d, date in zip(daschedule.values, roster_date):
        if d == 0:
            d = ""
        if date == "00:00:00":
            continue
        # room = 1
        output.append(
            {
                "clinic": location,
                "time_slot": shift,
                "date": date,
                "staff": "",
                "DAs": d,
                # "room": room,
            }
        )
        # room += 1
    return output

# get clinic location index
def get_location_index(roster):
    location_index = roster.loc[roster.loc[:, 1].notnull(), 1]  # remove HQ

    location_index_dict = {}
    for index, value in location_index.items():
        location_index_dict[value] = index
    return location_index_dict

# log success message
def success_message(record):
    print(
        "DR schedule created: DR {}, Clinic {}, date {}, session {}".format(
            record["staff"], record["clinic"], record["date"], record["time_slot"]
        )
    )

# get doctor reference from excel file
def get_dr_reference(filepath):
    ref = pd.read_excel(filepath, sheet_name="ABBV Ref", header=None)
    dr_ref = ref.loc[:, 15:16]
    dr_ref.columns = ["abb", "name"]
    dr_ref = dr_ref[~dr_ref["abb"].isna()]
    dr_ref = dr_ref.iloc[1:].reset_index(drop=True)
    return dr_ref

def get_da_reference(filepath):
    ref = pd.read_excel(filepath, sheet_name="ABBV Ref", header=None)
    da_ref = ref.loc[:, 11:12]
    da_ref.columns = ["abb", "name"]
    da_ref = da_ref[~da_ref["abb"].isna()]
    da_ref = da_ref.iloc[1:].reset_index(drop=True)
    return da_ref

def get_people_reference(table):
    data = []
    for i in table.all():
        data.append(i['fields']['Initials'])
    return data

# get raw doctor roster from excel file
def get_dr_roster(filepath):
    roster = pd.read_excel(filepath, sheet_name="Overall", header=None)
    return roster

# perform validation with ABB sheet
def dr_abb_validation(clean_roster_df, abb_list):
    error = []
    for _, row in clean_roster_df.iterrows():
        dr_list = row["staff"].split()
        for dr in dr_list:
            if dr not in abb_list:
                error.append(
                    {
                        "clinic": row["clinic"],
                        "time_slot": row["time_slot"],
                        "date": row["date"],
                        "staff": row["staff"],
                        "DAs": row["DAs"]
                    }
                )
    if len(error) != 0:
        return error
    else:
        return None

def da_abb_validation(clean_roster_df, abb_list):
    error = []
    for _, row in clean_roster_df.iterrows():
        row["DAs"] = str(row["DAs"])
        for ch in ['(', ')', 'nan']:
            if ch in row["DAs"]:
                row["DAs"] = row["DAs"].replace(ch, "")
        da_list = row["DAs"].split()
        for da in da_list:
            if da not in abb_list:
                error.append(
                    {
                        "clinic": row["clinic"],
                        "time_slot": row["time_slot"],
                        "date": row["date"],
                        "staff": row["staff"],
                        "DAs": row["DAs"]
                    }
                )
    if len(error) != 0:
        return error
    else:
        return None

# log validation error
def print_validation_error_records(error_list):
    for e in error_list:
        print(
            "Name error record: clinic {}, timeslot {}, date {}, name {}".format(
                e["clinic"], e["time_slot"], e["date"], e["staff"]
            )
        )

# check appointment title
def check_roster_title_format(title):
    return re.match(r"^DR \w+ (NIGHT|AM|PM)", title)
