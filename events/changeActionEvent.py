from logger import log
from constants import clientPackets
from constants import serverPackets
from objects import glob
from common.constants import mods

def handle(userToken, packetData):
	# Get usertoken data
	userID = userToken.userID
	username = userToken.username

	# Make sure we are not banned
	#if userUtils.isBanned(userID):
	#	userToken.enqueue(serverPackets.loginBanned())
	#	return

	# Send restricted message if needed
	#if userToken.restricted:
	#	userToken.checkRestricted(True)

	# Change action packet
	packetData = clientPackets.userActionChange(packetData)

	# If we are not in spectate status but we're spectating someone, stop spectating
	'''
if userToken.spectating != 0 and userToken.actionID != actions.WATCHING and userToken.actionID != actions.IDLE and userToken.actionID != actions.AFK:
	userToken.stopSpectating()

# If we are not in multiplayer but we are in a match, part match
if userToken.matchID != -1 and userToken.actionID != actions.MULTIPLAYING and userToken.actionID != actions.MULTIPLAYER and userToken.actionID != actions.AFK:
	userToken.partMatch()
		'''

	# Update cached stats if our pp changed if we've just submitted a score or we've changed gameMode
	#if (userToken.actionID == actions.PLAYING or userToken.actionID == actions.MULTIPLAYING) or (userToken.pp != userUtils.getPP(userID, userToken.gameMode)) or (userToken.gameMode != packetData["gameMode"]):

	# Update cached stats if we've changed gamemode
	if userToken.gameMode != packetData["gameMode"]:
		userToken.gameMode = packetData["gameMode"]
		userToken.updateCachedStats()

	# Always update action id, text, md5 and beatmapID
	userToken.actionID = packetData["actionID"]
	userToken.actionMd5 = packetData["actionMd5"]
	userToken.actionMods = packetData["actionMods"]
	userToken.beatmapID = packetData["beatmapID"]

	if userToken.actionID != 1:
		if packetData["actionMods"] & 128:
			# Only reload on mode change.
			if not userToken.relaxing: userToken.updateCachedStats()
			userToken.relaxing = True
			userToken.autopiloting = False
			userToken.actionText = "[RX] " + packetData["actionText"]
			userToken.updateCachedStats()
		#autopiloten
		elif packetData["actionMods"] & 8192:
			# Only reload on mode change.
			if not userToken.autopiloting: userToken.updateCachedStats()
			userToken.autopiloting = True
			userToken.relaxing = False
			userToken.actionText = "[AP] " + packetData["actionText"]
			userToken.updateCachedStats()
		else:
			if (not userToken.autopiloting) and (not userToken.relaxing):
				userToken.updateCachedStats()
			userToken.relaxing = False
			userToken.autopiloting = False
			userToken.actionText = "[VN] " + packetData["actionText"]
			userToken.updateCachedStats()
	
	# Enqueue our new user panel and stats to us and our spectators
	p = (
		serverPackets.userPanel(userID)
		+ serverPackets.userStats(userID)
	)
	userToken.enqueue(p)
	if userToken.spectators:
		for i in userToken.spectators:
			glob.tokens.tokens[i].enqueue(p)

	# Console output
	log.info(f"{username} updated their presence! [Action ID: {userToken.actionID} // Action Text: {userToken.actionText}]")
