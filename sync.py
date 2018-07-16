from __future__ import print_function
import httplib2
import os

import requests
from requests_ntlm import HttpNtlmAuth
from bs4 import BeautifulSoup
import json
from datetime import datetime
import rfc3339

from creds import USERNAME, PASSWORD

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Calendar API Python Quickstart'



class GuichetEtudiant:
    base_url = "https://inscription.uni.lu/Inscriptions/Student/GuichetEtudiant"

    def __init__(self, username, password):
        # initiate session and token variables
        self.__authenticate(username, password)

    def get_student_formation(self):
        return self.__session.post(
            GuichetEtudiant.base_url + "/getStudentFormation",
            data = {
                "__RequestVerificationToken": self.__token
            }
        )

    def get_events(self, start_date, end_date):
        # Get formation ids
        student_formation = self.get_student_formation()
        formations = json.loads(student_formation.content)
        formation_ids = [f["idForm"] for f in formations]

        # Format dates
        date_format = "%Y-%m-%dT00:00:00"    
        events = self.get_event_in_period(
            formation_ids,
            start_date.strftime(date_format),
            end_date.strftime(date_format)
        )

        # filter only needed keys
        # TODO: kinda complicated and cumbersome, should rewrite this
        keys = ["DateDebut", "DateFin", "Local", "Enseignant", "Cours", "Title", "LibelleType", "TypeCPE", "IsAllDay"]
        return [dict((key, value) for key, value in event.items() if key in keys) for event in events]

    
    def get_agenda_page(self):
        return self.__session.post(GuichetEtudiant.base_url + "/Agenda")


    def get_event_in_period(self, formation_ids, start_date, end_date):
        form_data = {
            "start": start_date,
            "end": end_date,
            "formations": formation_ids,
            "groupFilter": "all",
            "__RequestVerificationToken": self.__token
        }

        events_request = self.__session.post(
            GuichetEtudiant.base_url + "/getEventInPeriode", data=form_data
        )

        return json.loads(events_request.content)


    def __parse_verification_token(self, page):
        """ Expects page to be GuichetEtudiant Agenda page content and parses
            "__RequestVerificationToken" from XML data """

        soup = BeautifulSoup(page, "lxml")
        xmlData = soup.find(id="layout-data").get_text()

        for l in xmlData.split("\\r\\n"):
            if "__RequestVerificationToken" in l:
                input_field = BeautifulSoup(l, "html.parser").input
                return input_field["value"]

    
    def __authenticate(self, username, password):
        self.__session = requests.Session()
        self.__session.auth = HttpNtlmAuth('\\' + username, password)
        agenda = self.get_agenda_page()
        self.__token = self.__parse_verification_token(agenda.content)



# TODO: not sure if this is still needed
# def parseHeader(agenda_response):
#     cookies = agenda_response.headers["Set-Cookie"]
#     new_header = [xs.split("; ") for xs in cookies.split(", ") if xs.startswith("TS")][0]
#     h = new_header[0].split("=")
#     jar = agenda_response.cookies
#     jar[h[0]] = h[1]

#     return jar

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def find_calendar(service, calendar_name):
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            if calendar_list_entry['summary'] == calendar_name:
                return calendar_list_entry
            print(calendar_list_entry['summary'])
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    return None

def insert_events(service, calendar, events):
    """ Inserts events into the Google Calendar """
    date_fmt = "%Y/%m/%d %H:%M"
    for event in events:
        start_date = datetime.strptime(event["DateDebut"], date_fmt)
        end_date = datetime.strptime(event["DateFin"], date_fmt)
        event = {
            'summary': event["Title"],
            'location': event["Local"],
            'start': {
                'dateTime': rfc3339.rfc3339(start_date),
                'timeZone': 'Europe/Luxembourg'
            },
            'end': {
                'dateTime': rfc3339.rfc3339(end_date),
                'timeZone': 'Europe/Luxembourg'
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 15},
                ],
            },
        }
        service.events().insert(calendarId=calendar['id'], body=event).execute()


def clear_from_now(service, calendar):
    page_token = None
    event_ids = []
    date_min = rfc3339.rfc3339(datetime.now())
    events = service.events().list(calendarId=calendar["id"], pageToken=page_token, timeMin=date_min).execute()
    while True:
        for event in events["items"]:
            event_ids.append(event["id"])
            print(event["summary"])
        page_token = events.get("nextPageToken")
        if not page_token:
            break

    for eid in event_ids:
        service.events().delete(calendarId=calendar["id"], eventId=eid).execute()

        
def main():
    # start_date = datetime.now()
    # end_date = datetime(year=2018, month=3, day=30)
    
    start_date = datetime(year=2018, month=1, day=30)
    end_date = datetime(year=2018, month=3, day=30)
    
    ge = GuichetEtudiant(USERNAME, PASSWORD)
    print(ge.get_events(start_date, end_date))
    
    # credentials = get_credentials()
    # http = credentials.authorize(httplib2.Http())
    # service = discovery.build('calendar', 'v3', http=http)

    # cal = find_calendar(service, "University")
    # if not cal:
    #     raise ValueError("No given calendar found")

    # print("Clearing {} calendar".format(cal["summary"]))
    # clear_from_now(service, cal)
    
    # print("Event count:", len(events))
    # insert_events(service, cal, events)



if __name__ == '__main__':
    main()
