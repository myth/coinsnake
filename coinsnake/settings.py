# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-07
#
# settings.py is a part of coinsnake and is licenced under the MIT licence.

import os

# Logging

LOGDIR = 'logs'
LOGLEVEL = 'info'

# Web server

COINSTREAM_HOSTNAME = '127.0.0.1'
COINSTREAM_PORT = 9090

# Prices

PRICE_HISTORY_RESOLUTION = 60

# Exchanges

POLONIEX = {
    'push_api': {
        'auto_ping_interval': 15.0,
        'auto_ping_timeout': 30.0,
        'open_handshake_timeout': 60.0,
        'close_handshake_timeout': 60.0,
    },
    'pull_api': {
        'max_concurrent_connections': 2,
    }
}


def init_settings(cli_args=None) -> None:
    """
    Initializes the settings module with overrides from argparser
    :param cli_args: An ArgumentParser NameSpace object
    :return: None
    """

    if cli_args is not None:
        global LOGLEVEL
        if cli_args.verbose:
            LOGLEVEL = 'debug'
        elif cli_args.quiet:
            LOGLEVEL = 'warning'

    if not os.path.exists(LOGDIR):
        os.mkdir(LOGDIR)

    if cli_args.hostname is not None:
        global COINSTREAM_HOSTNAME
        COINSTREAM_HOSTNAME = cli_args.hostname
    if cli_args.port is not None:
        global COINSTREAM_PORT
        COINSTREAM_PORT = cli_args.port

