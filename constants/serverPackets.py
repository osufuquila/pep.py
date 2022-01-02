""" Contains functions used to write specific server packets to byte streams """
from common.constants import privileges
from common.ripple import userUtils
from constants import dataTypes
from constants import packetIDs
from constants import userRanks
from helpers import packetHelper
from objects import glob
from constants.rosuprivs import (
	OWNER,
	BAT,
	MODERATOR,
	DEVELOPER,
	DEV_SUPPORTER
)

""" Login errors packets """
def loginFailed():
	#return packetHelper.buildPacket(packetIDs.server_userID, ((-1, dataTypes.SINT32)))
	return b'\x05\x00\x00\x04\x00\x00\x00\xff\xff\xff\xff'

def forceUpdate():
	#return packetHelper.buildPacket(packetIDs.server_userID, ((-2, dataTypes.SINT32)))
	return b'\x05\x00\x00\x04\x00\x00\x00\xfe\xff\xff\xff'

def loginBanned():
	return b'\x05\x00\x00\x04\x00\x00\x00\xff\xff\xff\xff\x18\x00\x00@\x00\x00\x00\x0b>You are banned! Please contact us on Discord (link at ussr.pl)'

def loginLocked():
	return b'\x05\x00\x00\x04\x00\x00\x00\xff\xff\xff\xff\x18\x00\x00A\x00\x00\x00\x0b?Well... Your account is locked but all your data is still safe.'

def loginError():
	return b'\x05\x00\x00\x04\x00\x00\x00\xfb\xff\xff\xff'

def loginCheats():
	return b"\x18\x00\x00L\x00\x00\x00\x0bJWe don't like cheaters here at RealistikOsu! Consider yourself restricted.\x05\x00\x00\x04\x00\x00\x00\xff\xff\xff\xff"

def needSupporter():
	return b'\x05\x00\x00\x04\x00\x00\x00\xfa\xff\xff\xff'

def needVerification():
	return b'\x05\x00\x00\x04\x00\x00\x00\xf8\xff\xff\xff'


""" Login packets """
def userID(uid):
	return packetHelper.buildPacket(packetIDs.server_userID, ((uid, dataTypes.SINT32),))

def silenceEndTime(seconds):
	return packetHelper.buildPacket(packetIDs.server_silenceEnd, ((seconds, dataTypes.UINT32),))

def protocolVersion(version = 19):
	# This is always 19 so we might as well
	#return packetHelper.buildPacket(packetIDs.server_protocolVersion, ((version, dataTypes.UINT32)))
	return b'K\x00\x00\x04\x00\x00\x00\x13\x00\x00\x00'

def mainMenuIcon(icon):
	return packetHelper.buildPacket(packetIDs.server_mainMenuIcon, ((icon, dataTypes.STRING),))

def userSupporterGMT(supporter, GMT, tournamentStaff):
	result = 1
	if supporter:
		result |= userRanks.SUPPORTER
	if GMT:
		result |= userRanks.BAT
	if tournamentStaff:
		result |= userRanks.TOURNAMENT_STAFF
	return packetHelper.buildPacket(packetIDs.server_supporterGMT, ((result, dataTypes.UINT32),))

def friendList(userID):
	friends = userUtils.getFriendList(userID)
	return packetHelper.buildPacket(packetIDs.server_friendsList, ((friends, dataTypes.INT_LIST),))

def onlineUsers():
	userIDs = []

	# Create list with all connected (and not restricted) users
	for _, value in glob.tokens.tokens.items():
		if not value.restricted:
			userIDs.append(value.userID)

	return packetHelper.buildPacket(packetIDs.server_userPresenceBundle, ((userIDs, dataTypes.INT_LIST),))


""" Users packets """
def userLogout(userID):
	return packetHelper.buildPacket(packetIDs.server_userLogout, ((userID, dataTypes.SINT32), (0, dataTypes.BYTE),))

def userPanel(userID, force = False):
	# Connected and restricted check
	userToken = glob.tokens.getTokenFromUserID(userID)
	if userToken is None: return bytes()

	# Get user data
	username = userToken.username
	timezone = 24+userToken.timeOffset
	country = userToken.country
	gameRank = userToken.gameRank 
	latitude = userToken.getLatitude()
	longitude = userToken.getLongitude()

	# Get username colour according to rank
	# Only admins and normal users are currently supported
	userRank = 0
	if username == glob.BOT_NAME: userRank |= userRanks.ADMIN
	elif userToken.privileges == OWNER: userRank |= userRanks.PEPPY
	elif userToken.privileges in (DEVELOPER, DEV_SUPPORTER): userRank |= userRanks.ADMIN
	elif userToken.privileges == MODERATOR: userRank |= userRanks.MOD
	elif userToken.privileges & privileges.USER_DONOR: userRank |= userRanks.SUPPORTER
	else: userRank |= userRanks.NORMAL

	return packetHelper.buildPacket(packetIDs.server_userPanel,
	(
		(userID, dataTypes.SINT32),
		(username, dataTypes.STRING),
		(timezone, dataTypes.BYTE),
		(country, dataTypes.BYTE),
		(userRank, dataTypes.BYTE),
		(longitude, dataTypes.FFLOAT),
		(latitude, dataTypes.FFLOAT),
		(gameRank, dataTypes.UINT32)
	))


def userStats(userID, force = False):
	# Get userID's token from tokens list
	userToken = glob.tokens.getTokenFromUserID(userID)
	if userToken is None: return bytes()

	return packetHelper.buildPacket(packetIDs.server_userStats,
	(
		(userID, dataTypes.UINT32),
		(userToken.actionID, dataTypes.BYTE),
		(userToken.actionText, dataTypes.STRING),
		(userToken.actionMd5, dataTypes.STRING),
		(userToken.actionMods, dataTypes.SINT32),
		(userToken.gameMode, dataTypes.BYTE),
		(userToken.beatmapID, dataTypes.SINT32),
		(userToken.rankedScore, dataTypes.UINT64),
		(userToken.accuracy, dataTypes.FFLOAT),
		(userToken.playcount, dataTypes.UINT32),
		(userToken.totalScore, dataTypes.UINT64),
		(userToken.gameRank, dataTypes.UINT32),
		(userToken.pp if 65535 >= userToken.pp > 0 else 0, dataTypes.UINT16)
	))


""" Chat packets """
def sendMessage(fro, to, message):
	return packetHelper.buildPacket(packetIDs.server_sendMessage, (
		(fro, dataTypes.STRING),
		(message, dataTypes.STRING),
		(to, dataTypes.STRING),
		(userUtils.getID(fro), dataTypes.SINT32)
	))

def channelJoinSuccess(chan):
	return packetHelper.buildPacket(packetIDs.server_channelJoinSuccess, ((chan, dataTypes.STRING),))

def channelInfo(chan):
	if chan not in glob.channels.channels:
		return bytes()
	channel = glob.channels.channels[chan]
	return packetHelper.buildPacket(packetIDs.server_channelInfo, (
		(channel.name, dataTypes.STRING),
		(channel.description, dataTypes.STRING),
		(len(glob.streams.streams[f"chat/{chan}"].clients), dataTypes.UINT16)
	))

def channelInfoEnd():
	return b'Y\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00'

def channelKicked(chan):
	return packetHelper.buildPacket(packetIDs.server_channelKicked, ((chan, dataTypes.STRING),))

def userSilenced(userID):
	return packetHelper.buildPacket(packetIDs.server_userSilenced, ((userID, dataTypes.UINT32),))


""" Spectator packets """
def addSpectator(userID):
	return packetHelper.buildPacket(packetIDs.server_spectatorJoined, ((userID, dataTypes.SINT32),))

def removeSpectator(userID):
	return packetHelper.buildPacket(packetIDs.server_spectatorLeft, ((userID, dataTypes.SINT32),))

def spectatorFrames(data):
	return packetHelper.buildPacket(packetIDs.server_spectateFrames, ((data, dataTypes.BBYTES),))

def noSongSpectator(userID):
	return packetHelper.buildPacket(packetIDs.server_spectatorCantSpectate, ((userID, dataTypes.SINT32),))

def fellowSpectatorJoined(userID):
	return packetHelper.buildPacket(packetIDs.server_fellowSpectatorJoined, ((userID, dataTypes.SINT32),))

def fellowSpectatorLeft(userID):
	return packetHelper.buildPacket(packetIDs.server_fellowSpectatorLeft, ((userID, dataTypes.SINT32),))


""" Multiplayer Packets """
def createMatch(matchID):
	# Make sure the match exists
	if matchID not in glob.matches.matches:
		return bytes()

	# Get match binary data and build packet
	match = glob.matches.matches[matchID]
	matchData = match.getMatchData(censored=True)
	return packetHelper.buildPacket(packetIDs.server_newMatch, matchData)

# TODO: Add match object argument to save some CPU
def updateMatch(matchID, censored = False):
	# Make sure the match exists
	if matchID not in glob.matches.matches:
		return bytes()

	# Get match binary data and build packet
	match = glob.matches.matches[matchID]
	return packetHelper.buildPacket(packetIDs.server_updateMatch, match.getMatchData(censored=censored))

def matchStart(matchID):
	# Make sure the match exists
	if matchID not in glob.matches.matches:
		return bytes()

	# Get match binary data and build packet
	match = glob.matches.matches[matchID]
	return packetHelper.buildPacket(packetIDs.server_matchStart, match.getMatchData())

def disposeMatch(matchID):
	return packetHelper.buildPacket(packetIDs.server_disposeMatch, ((matchID, dataTypes.UINT32),))

def matchJoinSuccess(matchID):
	# Make sure the match exists
	if matchID not in glob.matches.matches:
		return bytes()

	# Get match binary data and build packet
	match = glob.matches.matches[matchID]
	data = packetHelper.buildPacket(packetIDs.server_matchJoinSuccess, match.getMatchData())
	return data

def matchJoinFail():
	return b'%\x00\x00\x00\x00\x00\x00'

def changeMatchPassword(newPassword):
	return packetHelper.buildPacket(packetIDs.server_matchChangePassword, ((newPassword, dataTypes.STRING),))

def allPlayersLoaded():
	return b'5\x00\x00\x00\x00\x00\x00'

def playerSkipped(userID):
	return packetHelper.buildPacket(packetIDs.server_matchPlayerSkipped, ((userID, dataTypes.SINT32),))

def allPlayersSkipped():
	return b'=\x00\x00\x00\x00\x00\x00'

def matchFrames(slotID, data):
	return packetHelper.buildPacket(packetIDs.server_matchScoreUpdate, ((data[7:11], dataTypes.BBYTES), (slotID, dataTypes.BYTE), (data[12:], dataTypes.BBYTES)))

def matchComplete():
	return b':\x00\x00\x00\x00\x00\x00'

def playerFailed(slotID):
	return packetHelper.buildPacket(packetIDs.server_matchPlayerFailed, ((slotID, dataTypes.UINT32),))

def matchTransferHost():
	return b'2\x00\x00\x00\x00\x00\x00'

def matchAbort():
	return b'j\x00\x00\x00\x00\x00\x00'

def switchServer(address):
	return packetHelper.buildPacket(packetIDs.server_switchServer, ((address, dataTypes.STRING),))

""" Other packets """
def notification(message):
	return packetHelper.buildPacket(packetIDs.server_notification, ((message, dataTypes.STRING),))

def banchoRestart(msUntilReconnection):
	return packetHelper.buildPacket(packetIDs.server_restart, ((msUntilReconnection, dataTypes.UINT32),))

def rtx(message):
	return packetHelper.buildPacket(0x69, ((message, dataTypes.STRING),))

def crash():
	#return buildPacket(packetIDs.server_supporterGMT, ((128, dataTypes.UINT32))) + buildPacket(packetIDs.server_ping)
	return b'G\x00\x00\x04\x00\x00\x00\x80\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00'
