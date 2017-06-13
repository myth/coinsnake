# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-07
#
# poloniex.py is a part of coinsnake and is licenced under the MIT licence

from time import time

import txaio
from autobahn.twisted.component import Component, run
from treq import json_content
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater

from coinsnake.price import PriceTracker
from coinsnake.settings import POLONIEX
from coinsnake.web.client import WebClient


class Poloniex(object):
    """
    Constructs a Poloniex API object that supports the Push API WAMP (WebSockets) protocol,
    as well as the standard HTTP REST API.
    """

    push_api = Component(
        realm='realm1',
        transports=[
            {
                'url': 'wss://api.poloniex.com',
                'type': 'websocket',
                'options': POLONIEX.get('push_api', dict()),
                'serializers': ['json'],
            }
        ],
    )
    price_tracker = PriceTracker()
    web_client = WebClient()

    def __init__(self):
        """
        Construct a Poloniex API wrapper
        """

        self.log = txaio.make_logger()

        # Register all event listeners and map to local methods
        Poloniex.push_api.on_connect(self.on_connect)
        Poloniex.push_api.on_join(self.on_join)
        Poloniex.push_api.on_leave(self.on_leave)
        Poloniex.push_api.on_disconnect(self.on_disconnect)

    def on_connect(self, *args, **kwargs):
        """
        WAMP Client tcp connect event
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        :return: None
        """

        self.log.info('Connected to Poloniex Push API')
        session, protocol = args
        self.log.debug(repr(session))
        self.log.debug(repr(protocol))
        self.log.debug('{}'.format(kwargs))

    def on_disconnect(self, *args, **kwargs):
        """
        WAMP Client tcp disconnect event
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        :return: None
        """

        self.log.info('Disconnected from Poloniex Push API')
        self.log.debug('{}'.format(args))
        self.log.debug('{}'.format(kwargs))

    @inlineCallbacks
    def on_join(self, *args, **kwargs):
        """
        Callback for when the WAMP client has successfully joined the Poloniex Push API.
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        :return: None
        """

        session, details = args

        self.log.info('Successfully joined Poloniex Push API, subcribing to ticker stream')
        self.log.debug(', '.join(repr(a) for a in args))
        self.log.debug(', '.join('%s:%s' % (repr(k), repr(v)) for k, v in kwargs))

        # Start periodically aggregating buffered price points to regular intervals
        self.price_tracker.start()

        yield session.subscribe(self.on_ticker, 'ticker')

    def on_leave(self, *args, **kwargs):
        """
        Callback for when we are leaving the Push API.
        :param args: Positional arguments
        :param kwargs: Keyword arguments
        :return: None
        """

        self.log.info('Leaving Poloniex Push API session')
        self.log.debug(', '.join(repr(a) for a in args))
        self.log.debug(', '.join('%s:%s' % (repr(k), repr(v)) for k, v in kwargs))

        # Stop the periodic price point aggregation task, since we aren't receiving any input at the moment
        self.price_tracker.stop()

    def on_ticker(self, *args):
        """
        Callback for ticker events received from the Poloniex WAMP Push API.
        Events received are grouped in the following format:

        Event::

            (currency_pair, last price, lowest ask, highest bid, percent_change,
             base_volume, quote_volume, is_frozen, 24hr high, 24hr low)

        :param args: A tuple of key values for the currency pair
        :return: None
        """

        if len(args) == 10:
            self.log.debug('{0}: {1} A:{2} B:{3} {4} V:{5} H:{8} L:{9}'.format(*args))
            label, last, ask, bid, change, volume, adj_volume, is_frozen, high, low = args
            self.price_tracker.add(label, float(last))
        else:
            self.log.warn('Received ticker update of length {}: {}'.format(len(args), args))

    def get_all_tickers(self) -> None:
        """
        Fetches all tickers from the Poloniex public REST API.
        :return: None
        """

        self.log.info('Retrieving all ticker information')

        @inlineCallbacks
        def cb(response):
            tickers = yield json_content(response)

            # Add the latest exchange rate for each currency pair to initialize the price tracker
            for ticker, data in tickers.items():
                if data['isFrozen'] == '0':
                    self.price_tracker.add(ticker, float(data['last']))

            self.log.info('Finished processing all tickers')
            self.get_history_for_all_tickers()

        self.web_client.get('https://poloniex.com/public', cb, params={'command': 'returnTicker'})

    def get_history_for_all_tickers(self) -> None:
        """
        Fetches the history for all registered tickers, with an interval of 300 seconds between each price
        point. All price points are partitioned into 1min chunks in the price tracker.
        :return: None
        """

        self.log.info('Retrieving ticker history for {} tickers'.format(self.price_tracker.num_tickers))

        queue = []
        # Schedule requests for all registered tickers
        for ticker in self.price_tracker.tickers.keys():
            params = {
                'command': 'returnChartData',
                'currencyPair': ticker,
                'start': int(time() - 3240 * 60),
                'end': int(time()),
                'period': 300,
            }
            queue.append(params)

        @inlineCallbacks
        def cb(response):
            history = yield json_content(response)
            last = str(response.request.absoluteURI).split('?')
            last = last[1]
            last = last.split('&')
            last = [x.split('=') for x in last]
            for a, b in last:
                if a == 'currencyPair':
                    last = b
                    break

            # Add the entire price history for this currency pair
            self.price_tracker.add_all(last, map(lambda x: x.get('close', 0.0), history), 300)

            if queue:
                deferLater(
                    reactor,
                    0.5,
                    self.web_client.get,
                    'https://poloniex.com/public',
                    cb,
                    params=queue.pop(0)
                )
            else:
                # Start running all components
                run(self.push_api)

            self.log.info('Processed {} price points for {}'.format(len(history), last))

        if queue:
            self.web_client.get('https://poloniex.com/public', cb, params=queue.pop(0))
