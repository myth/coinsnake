# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-13
#
# webserver.py is a part of coinsnake and is licenced under the MIT licence.

from autobahn.twisted.websocket import listenWS, WebSocketServerFactory, WebSocketServerProtocol
from twisted.internet import reactor
from txaio import start_logging


class CoinStreamProtocol(WebSocketServerProtocol):
    """
    Handles communication with metrics and diagnostics clients
    """

    def __init__(self):
        """
        Construct a CoinStreamProtocol
        """
        super().__init__()

    def onMessage(self, payload, is_binary) -> None:
        """
        Message handler
        :param payload: Raw message payload
        :param is_binary: Whether or not it was sent as a binary object
        :return: None
        """

        if not is_binary:
            msg = "{} from {}".format(payload.decode('utf8'), self.peer)
            self.factory.broadcast(msg)

    def onOpen(self) -> None:
        """
        Opened connection
        :return: None
        """

        self.log.debug('Connection established')
        self.factory.register(self)

    def connectionLost(self, reason) -> None:
        """
        Disconnect handler
        :param reason: Error message
        :return: None
        """

        super().connectionLost(reason)
        self.factory.unregister(self)


class CoinStreamServerFactory(WebSocketServerFactory):
    """
    Metrics and diagnostics server that streams all ticker and analysis events to clients
    """

    def __init__(self, *args, **kwargs):
        """
        Construct a CoinStreamServerFactory
        """
        super().__init__(*args, **kwargs)

        self.clients = []

    def register(self, client) -> None:
        """
        Registers a client to this server
        :param client: A client implementing the web socket protocol
        :return: None
        """

        if client not in self.clients:
            self.clients.append(client)
            self.log.info('Client connected: {}'.format(client.peer))

    def unregister(self, client) -> None:
        """
        Removes a client from this server
        :param client: A client implememnting the web socket protocol
        :return: None
        """

        if client in self.clients:
            self.clients.remove(client)
            self.log.info('Client disconnected: {}'.format(client.peer))

    def broadcast(self, message) -> None:
        """
        Broadcasts a message to all registered clients on this server
        :param message: A text message to be sent
        :return: None
        """

        for client in self.clients:
            client.sendMessage(message.encode('utf8'))

        self.log.debug('Message of {} bytes broadcasted to {} clients'.format(len(message), len(self.clients)))


def make_server(host: str, port: int) -> CoinStreamServerFactory:
    """
    Builds a CoinStreamServerFactory instance and hooks it up to the reactor
    :param host: Hostname to bind socket to (e.g ws://localhost or wss://some.host.com)
    :param port: Port to bind to
    :return: A CoinStreamServerFactory instance
    """

    if 'ws://' not in host and 'wss://' not in host:
        host = 'ws://{}'.format(host)

    host = '{}:{}'.format(host, port)

    cssf = CoinStreamServerFactory(host)
    cssf.protocol = CoinStreamProtocol
    listenWS(cssf)

    return cssf

if __name__ == '__main__':
    server = make_server('ws://127.0.0.1', 9090)
    start_logging()
    reactor.run()
