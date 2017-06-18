# -*- coding: utf8 -*-
#
# Created by 'myth' on 2017-06-15
#
# message.py is a part of coinsnake and is licenced under the MIT licence.

from datetime import datetime
import json


def create_envelope(payload: dict) -> dict:
    """
    Creates a dictionary with event label, timestamp and message field
    :param payload: The payload dict
    :return: An event message dictionary
    """

    payload['timestamp'] = datetime.utcnow().timestamp()
    if 'event' not in payload:
        payload['event'] = 'cs.unknown'
    if 'message' not in payload:
        payload['message'] = None

    return payload


def serialize_message(payload) -> str:
    """
    Serializes a dictionary to JSON format and encodes as UTF-8
    :param payload: A dictionary containing the payload data
    :return: An UTF8 JSON-encoded string
    """

    return json.dumps(payload).encode('utf8')
