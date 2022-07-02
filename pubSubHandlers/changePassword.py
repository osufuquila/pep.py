# This handles removing cached passwords from cache when the user has their pass
# changed.
from __future__ import annotations

from common.redis import generalPubSubHandler

from logger import log
from objects import glob


class handler(generalPubSubHandler.generalPubSubHandler):
    def __init__(self):
        super().__init__()
        self.structure = {
            "user_id": 0,
        }

    def handle(self, data):
        data = super().parseData(data)
        if data is None:
            return
        glob.cached_passwords.pop(data["user_id"], None)
        log.info(f"Updated password for user ID: {data['user_id']}")
