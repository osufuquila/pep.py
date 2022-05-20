from objects import glob
from constants import serverPackets
from logger import log

def handle(userToken, packetData):
	# get token data
	userID = userToken.userID

	# Send spectator frames to every spectator
	streamName = f"spect/{userID}"
	glob.streams.broadcast(streamName, serverPackets.spectator_frames(packetData[7:]))
	log.debug("Broadcasting {}'s frames to {} clients".format(
		userID,
		len(glob.streams.streams[streamName].clients))
	)