# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-12
#
# price.py is a part of coinsnake and is licenced under the MIT licence.

import six
from twisted.internet import task
import txaio

from coinsnake.settings import PRICE_HISTORY_RESOLUTION


class PriceHistory(object):
    """
    PriceHistory performs bookkeeping on the variations in price over time for a given ticker
    """

    def __init__(self, ticker: str):
        """
        Construct a new PriceHistory instance
        :param ticker: Currency pair label
        """

        self.log = txaio.make_logger()
        self.ticker = ticker.upper()
        self.history = list()
        self.current = 0.0
        self._buffer = list()

    def add(self, price: float) -> None:
        """
        Record a price point
        :param price: The current value
        :return: None
        """

        self.current = price
        self._buffer.append(price)
        self.log.info(str(self))

    def process_buffer(self) -> None:
        """
        Averages out the price points in the buffer, and adds it as a one minute block in the price history
        for this currency pair.
        :return: None
        """

        if len(self._buffer) > 0:
            self.history.append(sum(self._buffer) / len(self._buffer))
        else:
            self.history.append(self.current)

        self._buffer.clear()

    def __str__(self) -> str:
        """
        String representation of this price history object, with 1, 5, 15, 60, 360, 720, 1440 and 2880 minutes
        intervals, up to the maximum available range.
        NB: This method assumes 60 second price history resolution.
        :return: String representation of this price history object
        """

        fmt_string = '{}: {:.8f}'.format(self.ticker, self.current)
        intervals = (1, 5, 15, 60, 360, 720, 1440, 2880)

        for i, val in enumerate(intervals):
            if len(self.history) > val:
                # Swap from minutes to hours when we have enough records
                if val < 60:
                    fmt_string += ' %dm: {:.2f}%%' % val
                else:
                    fmt_string += ' %dh: {:.2f}%%' % (val / 60)
            else:
                # If we cannot compare two points, just return the current value
                if i == 0:
                    return fmt_string
                else:
                    # Calculates the percent wise change from the current price to the different time intervals
                    changes = (
                        (self.current - self.history[-1 * x]) * 100 / self.history[-1 * x] for x in intervals[:i]
                    )

                    return fmt_string.format(*changes)


class PriceTracker(object):
    """
    A PriceTracker maintains a table of ticker exchange rate history, with various metrics available
    """

    def __init__(self):
        """
        Construct a new PriceTracker instance
        """

        self.log = txaio.make_logger()
        self.tickers = dict()
        self._process_buffers_task = None

    def add(self, ticker_label: str, price: float) -> None:
        """
        Registers a new price value for a given currency pair
        :param ticker_label: The label for the currency pair
        :param price: The current price value
        :return: None
        """

        if type(ticker_label) not in six.string_types:
            error_msg = 'ticker_label type {} not in {}'.format(type(ticker_label), six.string_types)
            self.log.error(error_msg)

            raise TypeError(error_msg)

        if not isinstance(price, float):
            error_msg = 'price type {} not a float'.format(type(price))
            self.log.error(error_msg)

            raise TypeError(error_msg)

        if ticker_label not in self.tickers:
            self.tickers[ticker_label] = PriceHistory(ticker_label)

        self.tickers[ticker_label].add(price)

    def get(self, ticker_label: str) -> PriceHistory:
        """
        Retrieve the price history object for a given currency pair
        :param ticker_label: The ticker label for the currency pair
        :return: The corresponding PriceHistory for the currency pair
        """

        if ticker_label not in self.tickers:
            self.tickers[ticker_label] = PriceHistory(ticker_label)

        return self.tickers[ticker_label]

    def start(self) -> None:
        """
        Starts (if inactive) a recurring task that processes the accumulated price buffers for all registered
        currency pairs. The price intervals/resolution is specified in the settings.py file.
        :return: None
        """

        if self._process_buffers_task is None:
            self._process_buffers_task = task.LoopingCall(self._process_buffers)
            self._process_buffers_task.start(PRICE_HISTORY_RESOLUTION, now=False)
            self.log.info('Started price buffer processing at {} second interval'.format(PRICE_HISTORY_RESOLUTION))

    def stop(self) -> None:
        """
        Stops (if active) the recurring task that processes the accumulated price buffers for all registered
        currency pairs.
        :return:
        """

        if self._process_buffers_task is not None and self._process_buffers_task.running:
            self._process_buffers_task.stop()
            self._process_buffers_task = None
            self.log.info('Stopped price buffer processing task')

    def _process_buffers(self) -> None:
        """
        Aggregates buffered price points for all registered currency pairs
        :return: None
        """

        self.log.info('Processing price buffers')

        for ticker in self.tickers.values():
            ticker.process_buffer()
