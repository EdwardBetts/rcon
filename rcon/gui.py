"""GTK based GUI."""

from json import dump, load
from logging import basicConfig, getLogger
from os import getenv, name
from pathlib import Path
from socket import timeout
from typing import NamedTuple

from gi import require_version
require_version('Gtk', '3.0')
# pylint: disable=C0413
from gi.repository import Gtk

from rcon.config import LOG_FORMAT, LOGGER
from rcon.exceptions import RequestIdMismatch, WrongPassword
from rcon.proto import Client


__all__ = ['main']


if name == 'posix':
    CACHE_DIR = Path.home().joinpath('.cache')
elif name == 'nt':
    CACHE_DIR = Path(getenv('TEMP') or getenv('TMP'))
else:
    raise NotImplementedError('Unsupported operating system.')


CACHE_FILE = CACHE_DIR.joinpath('rcongui.json')
LOGGER = getLogger('rcongui')


class RCONParams(NamedTuple):
    """Represents the RCON parameters."""

    host: str
    port: int
    passwd: str
    command: str


class GUI(Gtk.Window):  # pylint: disable=R0902
    """A GTK based GUI for RCON."""

    def __init__(self):
        """Initializes the GUI."""
        super().__init__(title='RCON GUI')

        self.set_position(Gtk.WindowPosition.CENTER)

        self.grid = Gtk.Grid()
        self.add(self.grid)

        self.host = Gtk.Entry()
        self.host.set_placeholder_text('Host')
        self.grid.attach(self.host, 0, 0, 1, 1)

        self.port = Gtk.Entry()
        self.port.set_placeholder_text('Port')
        self.grid.attach(self.port, 1, 0, 1, 1)

        self.passwd = Gtk.Entry()
        self.passwd.set_placeholder_text('Password')
        self.passwd.set_visibility(False)
        self.grid.attach(self.passwd, 2, 0, 1, 1)

        self.command = Gtk.Entry()
        self.command.set_placeholder_text('Command')
        self.grid.attach(self.command, 0, 1, 2, 1)

        self.button = Gtk.Button(label='Run')
        self.button.connect('clicked', self.on_button_clicked)
        self.grid.attach(self.button, 2, 1, 1, 1)

        self.result = Gtk.Entry()
        self.result.set_placeholder_text('Result')
        self.grid.attach(self.result, 0, 2, 2, 1)

        self.savepw = Gtk.CheckButton(label='Save password')
        self.grid.attach(self.savepw, 2, 2, 1, 1)

        self.load_gui_settings()

    @property
    def gui_settings(self) -> dict:
        """Returns the GUI settings as a dict."""
        json = {
            'host': self.host.get_text(),
            'port': self.port.get_text(),
            'command': self.command.get_text(),
            'result': self.result.get_text(),
            'savepw': (savepw := self.savepw.get_active())
        }

        if savepw:
            json['passwd'] = self.passwd.get_text()

        return json

    @gui_settings.setter
    def gui_settings(self, json: dict):
        """Sets the GUI settings."""
        self.host.set_text(json.get('host', ''))
        self.port.set_text(json.get('port', ''))
        self.passwd.set_text(json.get('passwd', ''))
        self.command.set_text(json.get('command', ''))
        self.result.set_text(json.get('result', ''))
        self.savepw.set_active(json.get('savepw', False))

    def load_gui_settings(self) -> dict:
        """Loads the GUI settings from the cache file."""
        try:
            with CACHE_FILE.open('r') as cache:
                self.gui_settings = load(cache)
        except FileNotFoundError:
            LOGGER.warning('Cache file not found: %s', CACHE_FILE)
        except PermissionError:
            LOGGER.error('Insufficient permissions to read: %s', CACHE_FILE)
        except ValueError:
            LOGGER.error('Cache file contains garbage: %s', CACHE_FILE)

    def save_gui_settings(self):
        """Saves the GUI settings to the cache file."""
        try:
            with CACHE_FILE.open('w') as cache:
                dump(self.gui_settings, cache)
        except PermissionError:
            LOGGER.error('Insufficient permissions to read: %s', CACHE_FILE)

    def show_error(self, message: str):
        """Shows an error message."""
        message_dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message)
        message_dialog.run()
        message_dialog.destroy()

    def get_rcon_params(self) -> RCONParams:
        """Returns all settings as a dict."""
        if not (host := self.host.get_text()):  # pylint: disable=C0325
            raise ValueError('No host specified.')

        if not (port := self.port.get_text()):  # pylint: disable=C0325
            raise ValueError('No port specified.')

        if not (command := self.command.get_text()):    # pylint: disable=C0325
            raise ValueError('No command entered.')

        try:
            port = int(port)
        except ValueError:
            raise ValueError('Invalid port specified.') from None

        if not 0 <= port <= 65535:
            raise ValueError('Invalid port specified.')

        return RCONParams(host, port, self.passwd.get_text(), command)

    def run_rcon(self) -> str:
        """Returns the current RCON settings."""
        params = self.get_rcon_params()

        with Client(params.host, params.port, passwd=params.passwd) as client:
            return client.run(params.command)

    def on_button_clicked(self, _):
        """Runs the client."""
        try:
            result = self.run_rcon()
        except ValueError as error:
            self.show_error(' '.join(error.args))
        except ConnectionRefusedError:
            self.show_error('Connection refused.')
        except timeout:
            self.show_error('Connection timed out.')
        except RequestIdMismatch:
            self.show_error('Request ID mismatch.')
        except WrongPassword:
            self.show_error('Invalid password.')
        else:
            self.result.set_text(result)

    def terminate(self, *args, **kwargs):
        """Saves the settings and terminates the application."""
        self.save_gui_settings()
        Gtk.main_quit(*args, **kwargs)


def main():
    """Starts the GUI."""

    basicConfig(format=LOG_FORMAT)
    win = GUI()
    win.connect('destroy', win.terminate)
    win.show_all()
    Gtk.main()