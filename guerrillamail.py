#!/usr/bin/env python

import argparse
import json
from os.path import expanduser
import sys

import requests


class GuerrillaMailException(Exception):
    def __init__(self, *args, **kwargs):
        super(GuerrillaMailException, self).__init__(*args, **kwargs)


class GuerrillaMailSession(object):
    """
    An abstraction over a GuerrillamailClient which maintains session state.

    This class is not thread safe.
    """
    def __init__(self, session_id=None, **kwargs):
        self.client = GuerrillaMailClient(**kwargs)
        self.session_id = session_id

    def _update_session_id(self, response_data):
        try:
            self.session_id = response_data['sid_token']
        except KeyError:
            pass

    def _delegate_to_client(self, method_name, *args, **kwargs):
        client_method = getattr(self.client, method_name)
        response_data = client_method(session_id=self.session_id, *args, **kwargs)
        self._update_session_id(response_data)
        return response_data

    def get_email_address(self):
        data = self._delegate_to_client('get_email_address')
        return data['email_addr']

    def get_email_list(self, offset=0):
        response_data = self._delegate_to_client('get_email_list', offset=offset)
        email_list = response_data.get('list')
        return email_list if email_list else []

    def get_email(self, email_id):
        return self._delegate_to_client('get_email', email_id=email_id)


class GuerrillaMailClient(object):
    """
    A client to the Guerrillamail web service API
    (https://www.guerrillamail.com/GuerrillaMailAPI.html).
    """
    def __init__(self, base_url='http://api.guerrillamail.com', client_ip='127.0.0.1'):
        self.base_url = base_url
        self.client_ip = client_ip

    def _do_request(self, session_id, **kwargs):
        url = self.base_url + '/ajax.php'
        kwargs['ip'] = self.client_ip
        if session_id is not None:
            kwargs['sid_token'] = session_id
        response = requests.get(url, params=kwargs)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise GuerrillaMailException(e)
        data = json.loads(response.text)
        return data

    def get_email_address(self, session_id=None):
        return self._do_request(session_id, f='get_email_address')

    def get_email_list(self, session_id=None, offset=0):
        return self._do_request(session_id, f='get_email_list', offset=offset)

    def get_email(self, email_id, session_id=None):
        return self._do_request(session_id, f='fetch_email', email_id=email_id)


SETTINGS_FILE = '~/.guerrillamail'


def load_settings():
    try:
        with open(expanduser(SETTINGS_FILE)) as f:
            return json.load(f)
    except IOError:
        return {}


def save_settings(settings):
    with open(expanduser(SETTINGS_FILE), 'w+') as f:
        json.dump(settings, f)


class Command(object):
    params = []


class GetAddressCommand(Command):
    name = 'address'
    help = 'Get the current email address'
    description = 'Get the email address of the current Guerrillamail session'
    
    def invoke(self, session, args):
        return session.get_email_address()
    
    
class ListEmailCommand(Command):
    name = 'list'
    help = 'Get the current inbox contents'
    description = 'Get the contents of the inbox associated with the current session'
    
    def invoke(self, session, args):
        email_list = session.get_email_list()
        return json.dumps(email_list, indent=2)


class GetEmailCommand(Command):
    name = 'get'
    help = 'Get an email message by id.'
    description = 'Get an email message by id. The email id need not be associated with the current session.'
    params = [{
        'name': 'id',
        'help': 'an email id'
    }]
    
    def invoke(self, session, args):
        email = session.get_email(args.id)
        return json.dumps(email, indent=2)


COMMANDS = [GetAddressCommand(), ListEmailCommand(), GetEmailCommand()]


def _create_args_parser():
    parser = argparse.ArgumentParser(description='''Call a Guerrillamail web service.
        All commands operate on the current Guerrillamail session which is stored in {0}. If a session does not exist or
        has timed out a new one will be created.'''.format(SETTINGS_FILE))
    subparsers = parser.add_subparsers(dest='command', metavar='<command>')
    for command in COMMANDS:
        command_parser = subparsers.add_parser(command.name, help=command.help, description=command.description)
        for param in command.params:
            command_parser.add_argument(param['name'], help=param['help'])
    return parser


def main(*args):
    parser = _create_args_parser()
    args = parser.parse_args(args)
    settings = load_settings()
    session = GuerrillaMailSession(**settings)
    command = [c for c in COMMANDS if c.name == args.command][0]
    print command.invoke(session, args)
    settings['session_id'] = session.session_id
    save_settings(settings)


if __name__ == '__main__':
    main(*sys.argv[1:])