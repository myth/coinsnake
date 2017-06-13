# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-13
#
# webclient.py is a part of coinsnake and is licenced under the MIT licence.

from treq import get, post
from twisted.internet.defer import DeferredSemaphore
from txaio import make_logger

from coinsnake.settings import POLONIEX


class WebClient(object):
    """
    Global web client for deferred HTTP requests
    """

    _lock = DeferredSemaphore(POLONIEX['pull_api']['max_concurrent_connections'])

    def __init__(self):
        """
        Construct a WebClient
        """
        self.log = make_logger()
        self._pending = list()

    def get(self, url, callback):
        """
        Retrieve the contents of a web page
        :param url: URL of the page
        :param callback: Response callback
        :return: A Deferred HTTP response
        """

        self.log.debug('HTTP GET {}'.format(url))

        d = self._lock.run(get, url)
        d.addCallback(callback)

        return d
