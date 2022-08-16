from __future__ import annotations

import json

import tornado.gen
import tornado.web
from common.web import requestsManager

from constants import exceptions
from helpers import systemHelper
from logger import log
from objects import glob


class handler(requestsManager.asyncRequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def asyncGet(self):
        statusCode = 400
        data = {"message": "unknown error"}
        try:
            # Check arguments
            if not requestsManager.checkArguments(self.request.arguments, ["k"]):
                raise exceptions.invalidArgumentsException()

            # Check ci key
            key = self.get_argument("k")
            if key is None or key != glob.conf.CI_KEY:
                raise exceptions.invalidArgumentsException()

            log.info("Ci event triggered!!")
            systemHelper.scheduleShutdown(
                5,
                False,
                "A new Bancho update is available and the server will be restarted in 5 seconds. Thank you for your patience.",
            )

            # Status code and message
            statusCode = 200
            data["message"] = "ok"
        except exceptions.invalidArgumentsException:
            statusCode = 400
            data["message"] = "invalid ci key"
        finally:
            # Add status code to data
            data["status"] = statusCode

            # Send response
            self.write(json.dumps(data))
            self.set_status(statusCode)
