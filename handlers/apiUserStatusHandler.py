import json

import tornado.web
import tornado.gen

from common.ripple import userUtils
from common.web import requestsManager
from constants import exceptions
from objects import glob

import random

class handler(requestsManager.asyncRequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.engine
    def asyncGet(self):
        #here we fetch the user id
        try:
            UserID = int(self.get_argument("id"))
        except:
            self.write(json.dumps({
                "status" : 400,
                "message" : "Invalid or no id passed."
            }))
            self.set_status(400)
            return 
        
        #next we grab the token
        UserToken = glob.tokens.getTokenFromUserID(UserID)
        #ok now we make sure there are no errors if its offline

        if UserToken == None:
            self.write(json.dumps({
                "status" : 200,
                "message" : "i dint even lknow in netherlands?",
                "Online" : False
            }))
            self.set_status(200)
            return 
        
        #ok now we just return the json containing relevant info ig
        self.write(json.dumps({
            "status" : 200,
            "message" : random.choice([
                "denmark is exist",
                "denmark doesnt exist",
                "the uk #1",
                "femboy simon will haunt your dreams",
                "dash is da(ni)sh"
            ]),
            "Online" : True,
            "ActionID" : UserToken.actionID,
            "BeatmapID" : UserToken.beatmapID,
            "Username" : UserToken.username
        }))
        self.set_status(200)
        return 
        