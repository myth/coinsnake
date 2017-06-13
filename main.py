# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-07
#
# main.py is a part of coinsnake and is licenced under the MIT licence.

import argparse
import sys

from twisted.internet import reactor
import txaio

from coinsnake import VERSION
from coinsnake.poloniex import Poloniex
from coinsnake.settings import init_settings, COINSTREAM_HOSTNAME, COINSTREAM_PORT
from coinsnake.web.server import make_server


def main() -> int:
    log = txaio.make_logger()
    parser = argparse.ArgumentParser(prog='CoinSnake')

    parser.add_argument('-H', '--hostname', type=str, default=None,
                        help='Specifies hostname to bind coin stream server to')
    parser.add_argument('-p', '--port', type=int, default=None,
                        help='Specifies port to bind coin stream server to')
    parser.add_argument('-q', '--quiet', action='store_true', help='Enable quiet output')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--version', action='version', version='%%(prog)s v%s' % VERSION,
                        help='Print version information and exit')

    args = parser.parse_args()
    init_settings(args)
    from coinsnake.settings import LOGLEVEL

    txaio.start_logging(level=LOGLEVEL)
    log.info('CoinSnake v%s' % VERSION)

    poloniex = Poloniex()
    poloniex.get_all_tickers()

    coinstream = make_server(COINSTREAM_HOSTNAME, COINSTREAM_PORT)

    reactor.run()

    return 0


if __name__ == '__main__':
    sys.exit(main())
