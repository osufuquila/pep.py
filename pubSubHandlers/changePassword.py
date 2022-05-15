# This handles removing cached passwords from cache when the user has their pass
# changed.
from common.redis import generalPubSubHandler
from objects import glob
from logger import log

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
