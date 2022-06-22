from __future__ import annotations

from helpers import chatHelper as chat
from logger import log
from objects import channel
from objects import glob


class ChannelList:
    def __init__(self):
        self.channels = {}

    def loadChannels(self):
        """
        Load chat channels from db and add them to channels list
        :return:
        """
        # Get channels from DB
        channels = glob.db.fetchAll("SELECT * FROM bancho_channels")

        # Add each channel if needed
        for i in channels:
            if i["name"] not in self.channels:
                publicRead = True if i["public_read"] == 1 else False
                publicWrite = True if i["public_write"] == 1 else False
                self.addChannel(i["name"], i["description"], publicRead, publicWrite)

    def addChannel(
        self,
        name,
        description,
        publicRead,
        publicWrite,
        temp=False,
        hidden=False,
    ):
        """
        Add a channel to channels list

        :param name: channel name
        :param description: channel description
        :param publicRead: if True, this channel can be read by everyone. If False, it can be read only by mods/admins
        :param publicWrite: same as public read, but regards writing permissions
        :param temp: if True, this channel will be deleted when there's no one in this channel
        :param hidden: if True, thic channel won't be shown in channels list
        :return:
        """
        glob.streams.add(f"chat/{name}")
        self.channels[name] = channel.Channel(
            name,
            description,
            publicRead,
            publicWrite,
            temp,
            hidden,
        )
        log.info(f"Created channel {name}")

    def addTempChannel(self, name):
        """
        Add a temporary channel (like #spectator or #multiplayer), gets deleted when there's no one in the channel
        and it's hidden in channels list

        :param name: channel name
        :return: True if the channel was created, otherwise False
        """
        if name in self.channels:
            return False
        glob.streams.add(f"chat/{name}")
        self.channels[name] = channel.Channel(name, "Chat", True, True, True, True)
        log.info(f"Created temp channel {name}")

    def addHiddenChannel(self, name):
        """
        Add a hidden channel. It's like a normal channel and must be deleted manually,
        but it's not shown in channels list.

        :param name: channel name
        :return: True if the channel was created, otherwise False
        """
        if name in self.channels:
            return False
        glob.streams.add(f"chat/{name}")
        self.channels[name] = channel.Channel(name, "Chat", True, True, False, True)
        log.info(f"Created hidden channel {name}")

    def removeChannel(self, name):
        """
        Removes a channel from channels list

        :param name: channel name
        :return:
        """
        if name not in self.channels:
            log.debug(f"{name} is not in channels list")
            return
        # glob.streams.broadcast("chat/{}".format(name), serverPackets.channel_kicked(name))
        stream = glob.streams.getStream(f"chat/{name}")
        if stream is not None:
            for token in stream.clients:
                if token in glob.tokens.tokens:
                    chat.partChannel(
                        channel=name,
                        token=glob.tokens.tokens[token],
                        kick=True,
                    )
        glob.streams.dispose(f"chat/{name}")
        glob.streams.remove(f"chat/{name}")
        self.channels.pop(name)
        log.info(f"Removed channel {name}")
