# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-13
#
# events.py is a part of coinsnake and is licenced under the MIT licence.

import json

import txaio

from coinsnake.message import create_envelope
from coinsnake.web.server import CoinStreamServerFactory

txaio.use_twisted()

VALID_EVENTS = (
    'cs.error',
    'cs.hello',
    'cs.message',
    'cs.user_count',
    'cs.unknown',
    'cs.ticker.update',
    'cs.ticker.labels',
    'cs.ticker.processing_buffers',
    'cs.poloniex.push_api.connecting',
    'cs.poloniex.push_api.connected',
    'cs.poloniex.push_api.disconnect',
    'cs.poloniex.push_api.join',
    'cs.poloniex.push_api.leave',
)


class EventDispatcher(object):
    """
    Handles different events and pushes them onto the CoinStream server
    """

    def __init__(self, coinstream_server):
        """
        Constructs an event dispatcher
        """

        from txaio import make_logger
        self.log = make_logger()

        if not isinstance(coinstream_server, CoinStreamServerFactory):
            self.log.error(
                'EventDispatcher did not receive a coinstream server, was {}'.format(type(coinstream_server))
            )
            raise ValueError('Argument "coinstream_server" must be an instance of CoinStreamServerFactory')

        self.server = coinstream_server

    def _handle_event(self, payload) -> None:
        """
        Transforms the payload to JSON, attaches the event label and dispatches to the coinstream broadcast server
        :param payload: A dictionary
        :return: None
        """

        if not isinstance(payload, dict):
            raise ValueError('EventDispatcher._handle_event "payload" argument must be a dict')

        payload = create_envelope(payload)
        self.server.broadcast(json.dumps(payload))

    def handle_ticker(self, ticker_label, ticker_string, **kwargs) -> None:
        """
        Handles ticker events from a Price Tracker
        :param ticker_label: The currency pair label
        :param ticker_string: The str() representation of a PriceHistory object
        :return: None
        """

        event = kwargs.get('event_label', 'cs.ticker.update')

        if event != 'cs.ticker.update':
            self.log.error('EventDispatcher.handle_ticker invoked with {} event'.format(event))
            raise ValueError('EventDispatcher.handle_ticker invoked with {} event'.format(event))

        currency, ticker = ticker_label.split('_')

        payload = {
            'event': 'cs.ticker.update',
            'ticker': ticker,
            'ticker_string': ticker_string,
            'currency': currency,
            'message': 'ticker updated'
        }

        self._handle_event(payload)

    def handle_generic_event(self, *args, **kwargs) -> None:
        """
        Handles generic events that have no specific structure
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        :return: None
        """

        event = kwargs.get('event_label', 'cs.unknown')
        kwargs['event'] = event
        del kwargs['event_label']

        if not isinstance(event, str):
            self.log.error('EventDispatcher.handle_generic_event invoked with non-string {} event'.format(event))
            raise ValueError('EventDispatcher.handle_generic_event invoked with non-string {} event'.format(event))

        if args:
            kwargs['details'] = [repr(a) for a in args]

        self._handle_event(kwargs)
