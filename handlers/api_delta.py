from __future__ import annotations

import json
import re
import traceback

import tornado.gen
import tornado.web
from common.web import requestsManager

from logger import log
from objects import glob

REGEX = re.compile(
    r"^(\[(?P<clan>.+)\]) (?P<name>.+) play (?P<artist>.+) - (?P<title>.+) (?:\((?P<creator>.+)\))?(?: \[(?P<version>.+)\])",
)


class handler(requestsManager.asyncRequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def asyncGet(self, user_id: int):
        try:
            # Fetch them from glob.
            user = glob.tokens.getTokenFromUserID(user_id)

            if not user:
                self.write(json.dumps({"code": 200, "clients": []}))
                return

            # Before data run regex to delete clan.
            action = user.actionText
            reg = REGEX.match(user.actionText)
            if reg and reg.groupdict().get("clan"):
                action = user.actionText.split("]", 1)[1]
            # Struct data.
            data = {
                "code": 200,
                "clients": [
                    {
                        "api_identifier": f"@{user.token}",
                        "type": 0,
                        "action": {
                            "id": user.actionID,
                            "text": action,
                            "beatmap": {"id": user.beatmapID},
                        },
                        "user_id": user.userID,
                        "location": "null",
                        "username": user.username,
                        "privileges": user.privileges,
                        "silence_end_time": user.silenceEndTime,
                    },
                ],
            }
            self.write(json.dumps(data))
        except Exception:  # Use exception.
            self.set_status(500)
            tb = traceback.format_exc()  # Use tracebacks for better error logging
            log.error(f"There was issue handling delta api request\n {tb}")
            self.write(
                json.dumps({"code": 500, "message": "Server got itself in troube..."}),
            )
