# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-13
#
# webclient.py is a part of coinsnake and is licenced under the MIT licence.

import json

from autobahn.twisted.websocket import connectWS, WebSocketClientFactory, WebSocketClientProtocol
from treq import get
from twisted.internet import reactor
from twisted.internet.defer import DeferredSemaphore
from txaio import make_logger, start_logging


class WebClient(object):
    """
    Global web client for deferred HTTP requests
    """

    def __init__(self, max_concurrent_conns=2):
        """
        Construct a WebClient
        """
        self.log = make_logger()
        self._lock = DeferredSemaphore(max_concurrent_conns)

    def get(self, url, callback, params=None):
        """
        Retrieve the contents of a web page
        :param url: URL of the page
        :param callback: Response callback
        :param params: GET url parameters
        :return: A Deferred HTTP response
        """

        self.log.debug('HTTP GET {}'.format(url))

        if params is None:
            params = dict()

        d = self._lock.run(get, url, params=params)
        d.addCallback(callback)

        return d


class WebSocketTestClient(WebSocketClientProtocol):
    """
    For debug purposes
    """

    def __init__(self):
        super().__init__()

    def send_hello(self):
        self.sendMessage('{"event": "cs.hello", "message": "Hello!"}'.encode('utf8'))

    def onOpen(self):
        self.log.info('Connection established')
        self.send_hello()

    def onMessage(self, payload, is_binary):
        if not is_binary:
            message = payload.decode('utf8')
            message_object = json.loads(message)
            print(repr(message_object))

if __name__ == '__main__':
    factory = WebSocketClientFactory('ws://127.0.0.1:9090')
    factory.protocol = WebSocketTestClient
    connectWS(factory)
    start_logging()

    reactor.run()
