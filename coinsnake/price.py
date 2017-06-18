# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-12
#
# price.py is a part of coinsnake and is licenced under the MIT licence.

import time
from typing import Iterable

from autobahn.util import ObservableMixin
import six
from twisted.internet import task
import txaio

from coinsnake.settings import PRICE_HISTORY_RESOLUTION

CHANGE_INTERVALS = (1, 5, 15, 60, 360, 720, 1440, 2880)


class PriceHistory(object):
    """
    PriceHistory performs bookkeeping on the variations in price over time for a given ticker.
    History is divided into tuples of (high, low, open, close, volume)
    Buffers are stored as tuples of (last, volume)
    """

    def __init__(self, ticker: str):
        """
        Construct a new PriceHistory instance
        :param ticker: Currency pair label
        """

        self.log = txaio.make_logger()
        self.ticker = ticker.upper()
        self.history = list()
        self.last = 1.0
        self._buffer = list()

    def add(self, price: float, volume: float) -> None:
        """
        Record a price point
        :param price: The current value
        :param volume: The volume reported in the ticker
        :return: None
        """

        self.last = price
        self._buffer.append((price, volume))
        self.log.info(str(self))

    @property
    def changes(self):
        """
        Returns a tuple of percent wise changes from now to the last
        1, 5, 15, 60, 120, 360, 720, 1440 and 2880 minutes.
        :return:
        """

        max_history = len(self.history)

        if max_history < 2:
            return tuple(0.0 for _ in CHANGE_INTERVALS)

        indexes = []
        for i, val in enumerate(CHANGE_INTERVALS):
            if val <= max_history:
                indexes.append(CHANGE_INTERVALS[i])
            else:
                indexes.append(indexes[i-1])

        # Index 3 in history tuples are the closing price
        return tuple((self.last - self.history[-1 * x][3]) * 100 / self.history[-1 * x][3] for x in indexes)

    def process_buffer(self) -> None:
        """
        Averages out the price points in the buffer, and adds it as a one minute block in the price history
        for this currency pair.
        :return: None
        """

        if self._buffer:
            p_value, p_volume = self._buffer.pop(0)

            p_high = p_value
            p_low = p_value
            p_open = p_value
            p_close = p_value

            for val, vol in self._buffer:
                if val < p_low:
                    p_low = val
                elif val > p_high:
                    p_high = val
                p_close = val
                p_volume += vol

            self.history.append((p_high, p_low, p_open, p_close, p_volume))
        else:
            self.history.append((self.last, self.last, self.last, self.last, 0.0))

        self._buffer.clear()

    def __str__(self) -> str:
        """
        String representation of this price history object, with 1, 5, 15, 60, 360, 720, 1440 and 2880 minutes
        intervals, up to the maximum available range.
        NB: This method assumes 60 second price history resolution.
        :return: String representation of this price history object
        """

        fmt_string = '{}: {:.8f}'.format(self.ticker, self.last)
        intervals = (1, 5, 15, 60, 360, 720, 1440, 2880)

        index = 0
        for i, val in enumerate(intervals):
            if len(self.history) > val:
                index += 1
                # Swap from minutes to hours when we have enough records
                if val < 60:
                    fmt_string += ' %dm: {:.2f}%%' % val
                else:
                    fmt_string += ' %dh: {:.2f}%%' % (val / 60)
            else:
                break

        return fmt_string.format(*self.changes)


class PriceTracker(ObservableMixin):
    """
    A PriceTracker maintains a table of ticker exchange rate history, with various metrics available
    """

    def __init__(self):
        """
        Construct a new PriceTracker instance
        """

        super().__init__()
        self.log = txaio.make_logger()
        self.tickers = dict()
        self._process_buffers_task = None

    def add(self, ticker_label: str, price: float, volume: float) -> None:
        """
        Registers a new price value for a given currency pair
        :param ticker_label: The label for the currency pair
        :param price: The current price value
        :param volume: The volume since last update
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

        if not isinstance(volume, float):
            error_msg = 'volume type {} not a float'.format(type(volume))
            self.log.error(error_msg)

            raise TypeError(error_msg)

        if ticker_label not in self.tickers:
            self.tickers[ticker_label] = PriceHistory(ticker_label)

        self.tickers[ticker_label].add(price, volume)
        self.fire('cs.ticker.update', ticker_label, str(self.tickers[ticker_label]), event_label='cs.ticker.update')

    def add_all(self, ticker_label: str, prices: Iterable, interval: int) -> None:
        """
        Registers all the provided price points, assuming they are aggregated over
        the provided interval (in seconds).
        Expects prices to be on (high, low, open, close, volume) format.
        Prices must be sorted with newest entries last.
        :param ticker_label: The label for the currency pair
        :param prices: A list of price points
        :param interval: The number of seconds elapsed between each price point
        :return: None
        """

        if ticker_label not in self.tickers:
            self.tickers[ticker_label] = PriceHistory(ticker_label)

        ph = self.tickers[ticker_label]

        price_points = []
        duplications = int(interval / PRICE_HISTORY_RESOLUTION)

        # For eace price interval, create copies to fill 1 minute intervals and spread values accordingly
        for p in prices:
            duplicated = list(list(p) for _ in range(duplications))
            p_close = p[3]
            for i in range(duplications):
                # Spread the total volume over all points
                duplicated[i][4] /= duplications
                # Set all close points to the open point, since we are saving the close value for last
                duplicated[i][3] = duplicated[i][2]

            duplicated[duplications - 1][3] = p_close

            price_points.extend(duplicated)

        ph.history = price_points
        ph.last = price_points[-1][3]

        self.log.info(str(ph))
        self.fire('cs.ticker.update', ticker_label, str(ph), event_label='cs.ticker.update')

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
            self._process_buffers_task = task.LoopingCall(self.process_buffers)
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

    @property
    def num_tickers(self) -> int:
        """
        Returns the number of registered tickers on this price tracker
        :return: An integer
        """

        return len(self.tickers)

    def process_buffers(self) -> None:
        """
        Aggregates buffered price points for all registered currency pairs
        :return: None
        """

        self.log.info('Processing price buffers')
        self.fire('cs.ticker.processing_buffers', event_label='cs.ticker.processing_buffers')

        start_time = time.time()

        for ticker in self.tickers.values():
            ticker.process_buffer()

        self.fire(
            'cs.message',
            event_label='cs.message',
            message='Price buffer processing took {:.3f} seconds.'.format(time.time() - start_time)
        )
