import json
import random
import re
import threading
from typing import Callable

import requests
import time

from common import generalUtils
from common.constants import mods
from logger import log
from common.ripple import userUtils
from constants import exceptions, slotStatuses, matchModModes, matchTeams, matchTeamTypes, matchScoringTypes
from common.constants import gameModes
from common.constants import privileges
from constants import serverPackets
from helpers import systemHelper
from objects import fokabot
from objects import glob
from helpers import chatHelper as chat
from datetime import datetime
from datetime import timedelta

commands = []

def registerCommand(trigger: str, syntax: str = None, privs: privileges = None, resp: str = None):
	"""A decorator to set commands into list."""
	global commands
	def wrapper(handler: Callable) -> Callable:
		commands.append({
			"trigger": trigger,
			"callback": handler,
			"syntax": syntax or "",
			"privileges": privs or None,
			"response": resp or ":thonk:"
		})
		return handler
	return wrapper


def chimuMessage(beatmapID):
	beatmap = glob.db.fetch("SELECT song_name, beatmapset_id FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
	return "Download [https://chimu.moe/en/d/{} {}] from Chimu".format(
		beatmap["beatmapset_id"],
		"Unknown Beatmap" if beatmap is None else beatmap["song_name"],
	)

def beatconnectMessage(beatmapID):
	beatmap = glob.db.fetch("SELECT song_name, beatmapset_id FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
	return "Download [https://beatconnect.io/b/{} {}] from Beatconnect".format(
		beatmap["beatmapset_id"],
		"Unknown Beatmap" if beatmap is None else beatmap["song_name"],
	)
	
def mirrorMessage(beatmapID):
	beatmap = glob.db.fetch("SELECT song_name, beatmapset_id FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
	return "Download {} from [https://beatconnect.io/b/{} Beatconnect], [https://chimu.moe/en/d/{} Chimu] or [osu://dl/{} osu!direct].".format(
		"Unknown Beatmap" if beatmap is None else beatmap["song_name"],
		beatmap["beatmapset_id"],
		beatmap["beatmapset_id"],
		beatmap["beatmapset_id"],
	)

def restartShutdown(restart):
	"""Restart (if restart = True) or shutdown (if restart = False) pep.py safely"""
	msg = "We are performing some maintenance. Bancho will {} in 5 seconds. Thank you for your patience.".format("restart" if restart else "shutdown")
	systemHelper.scheduleShutdown(5, restart, msg)
	return msg

def getMatchIDFromChannel(chan):
	if not chan.lower().startswith("#multi_"):
		raise exceptions.wrongChannelException()
	parts = chan.lower().split("_")
	if len(parts) < 2 or not parts[1].isdigit():
		raise exceptions.wrongChannelException()
	matchID = int(parts[1])
	if matchID not in glob.matches.matches:
		raise exceptions.matchNotFoundException()
	return matchID

def getSpectatorHostUserIDFromChannel(chan):
	if not chan.lower().startswith("#spect_"):
		raise exceptions.wrongChannelException()
	parts = chan.lower().split("_")
	if len(parts) < 2 or not parts[1].isdigit():
		raise exceptions.wrongChannelException()
	userID = int(parts[1])
	return userID

def getPPMessage(userID, just_data = False):
	"""Display PP stats for a map."""
	try:
		# Get user token
		token = glob.tokens.getTokenFromUserID(userID)
		if token is None:
			return False

		currentMap = token.tillerino[0]
		currentMods = token.tillerino[1]
		currentAcc = token.tillerino[2]

		# Send request to LETS api
		url = "{}/v1/pp?b={}&m={}".format(glob.conf.config["server"]["letsapiurl"].rstrip("/"), currentMap, currentMods)
		resp = requests.get(url, timeout=10)
		try:
			assert resp is not None
			data = json.loads(resp.text)
		except (json.JSONDecodeError, AssertionError):
			raise exceptions.apiException()

		# Make sure status is in response data
		if "status" not in data:
			raise exceptions.apiException()

		# Make sure status is 200
		if data["status"] != 200:
			if "message" in data:
				return "There has been an exception the in PP API call ({}).".format(data["message"])
			else:
				raise exceptions.apiException()

		if just_data:
			return data

		# Return response in chat
		# Song name and mods
		msg = "{song}{plus}{mods}  ".format(song=data["song_name"], plus="+" if currentMods > 0 else "", mods=generalUtils.readableMods(currentMods))

		# PP values
		if currentAcc == -1:
			msg += "95%: {pp95}pp | 98%: {pp98}pp | 99% {pp99}pp | 100%: {pp100}pp".format(pp100=round(data["pp"][0], 2), pp99=round(data["pp"][1], 2), pp98=round(data["pp"][2], 2), pp95=round(data["pp"][3], 2))
		else:
			msg += "{acc:.2f}%: {pp}pp".format(acc=token.tillerino[2], pp=round(data["pp"][0], 2))
		
		originalAR = data["ar"]
		# calc new AR if HR/EZ is on
		if (currentMods & mods.EASY) > 0:
			data["ar"] = max(0, data["ar"] / 2)
		if (currentMods & mods.HARDROCK) > 0:
			data["ar"] = min(10, data["ar"] * 1.4)
		
		arstr = " ({})".format(originalAR) if originalAR != data["ar"] else ""
		
		# Beatmap info
		msg += " | {bpm} BPM | AR {ar}{arstr} | {stars:.2f} stars".format(bpm=data["bpm"], stars=data["stars"], ar=data["ar"], arstr=arstr)

		# Return final message
		return msg
	except requests.exceptions.RequestException:
		# RequestException
		return "API Timeout. Please try again in a few seconds."
	except exceptions.apiException:
		# API error
		return "Unknown error in LETS API call."
	#except:
		# Unknown exception
		# TODO: print exception
	#	return False
	
"""
Commands callbacks

Must have fro, chan and messages as arguments
:param fro: username of who triggered the command
:param chan: channel"(or username, if PM) where the message was sent
:param message: list containing arguments passed from the message
				[0] = first argument
				[1] = second argument
				. . .

return the message or **False** if there's no response by the bot
TODO: Change False to None, because False doesn't make any sense
"""
@registerCommand(trigger= "!ir", privs= privileges.ADMIN_MANAGE_SERVERS)
def instantRestart(fro, chan, message):
	"""Reloads pep.py instantly."""
	glob.streams.broadcast("main", serverPackets.notification("We are restarting Bancho. Be right back!"))
	systemHelper.scheduleShutdown(0, True, delay=5)
	return False

@registerCommand(trigger= "!roll")
def roll(fro, chan, message):
	"""Rolls a number between 0 and 100 (or provided number)."""
	maxPoints = 100
	if len(message) >= 1:
		if message[0].isdigit() and int(message[0]) > 0:
			maxPoints = int(message[0])

	points = random.randrange(0,maxPoints)
	return "{} rolls {} points!".format(fro, str(points))

@registerCommand(trigger= "!alert", syntax= "<message>", privs= privileges.ADMIN_SEND_ALERTS)
def alert(fro, chan, message):
	"""Sends a notification to all currently online members."""
	msg = ' '.join(message[:]).strip()
	if not msg:
		return False
	glob.streams.broadcast("main", serverPackets.notification(msg))
	return False

@registerCommand(trigger= "!alertuser", syntax= "<username> <message>", privs= privileges.ADMIN_SEND_ALERTS)
def alertUser(fro, chan, message):
	"""Sends a notification to a specific user."""

	target = message[0].lower()
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		msg = ' '.join(message[1:]).strip()
		if not msg:
			return False
		targetToken.enqueue(serverPackets.notification(msg))
		return False
	else:
		return "User offline."

@registerCommand(trigger= "!moderated", privs= privileges.ADMIN_CHAT_MOD)
def moderated(fro, chan, message):
	try:
		# Make sure we are in a channel and not PM
		if not chan.startswith("#"):
			raise exceptions.moderatedPMException

		# Get on/off
		enable = True
		if len(message) >= 1:
			if message[0] == "off":
				enable = False

		# Turn on/off moderated mode
		glob.channels.channels[chan].moderated = enable
		return "This channel is {} in moderated mode!".format("now" if enable else "no longer")
	except exceptions.moderatedPMException:
		return "You are trying to put a private chat in moderated mode. Are you serious?!? You're fired."

@registerCommand(trigger= "!kickall", privs= privileges.ADMIN_MANAGE_SERVERS)
def kickAll(fro, chan, message):
	"""Kicks all members from the server (except staff)."""
	# Kick everyone but mods/admins
	toKick = []
	with glob.tokens:
		for key, value in glob.tokens.tokens.items():
			if not value.admin:
				toKick.append(key)

	# Loop though users to kick (we can't change dictionary size while iterating)
	for i in toKick:
		if i in glob.tokens.tokens:
			glob.tokens.tokens[i].kick()

	return "Whoops! Who needs players anyways?"

@registerCommand(trigger= "!kick", syntax= "<target>", privs= privileges.ADMIN_KICK_USERS)
def kick(fro, chan, message):
	"""Kicks a specific member from the server."""
	# Get parameters
	target = message[0].lower()
	if target == glob.BOT_NAME.lower():
		return "Nope."

	# Get target token and make sure is connected
	tokens = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True, _all=True)
	if len(tokens) == 0:
		return "{} is not online".format(target)

	# Kick users
	for i in tokens:
		i.kick()

	# Bot response
	return "{} has been kicked from the server.".format(target)

@registerCommand(trigger= "!bot reconnect", privs= privileges.ADMIN_MANAGE_SERVERS)
def fokabotReconnect(fro, chan, message):
	"""Forces the bot to reconnect."""
	# Check if the bot is already connected
	if glob.tokens.getTokenFromUserID(999) is not None:
		return "{} is already connected to RealistikOsu!".format(glob.BOT_NAME)

	# Bot is not connected, connect it
	fokabot.connect()
	return False

@registerCommand(trigger= "!bot reload", privs= privileges.ADMIN_MANAGE_SERVERS)
def reload_commands(fro, chan, mes) -> str:
	"""Reloads all of the RealistikBot commands."""

	try:
		fokabot.reload_commands()
		return "RealistikBot has been reloaded successfully!"
	except Exception as e:

		return f"There has been an exception while reloading the bot: {e}"

@registerCommand(trigger= "!silence", syntax= "<target> <amount> <unit(s/m/h/d)> <reason>", privs= privileges.ADMIN_SILENCE_USERS)
def silence(fro, chan, message):
	"""Silences a specific user for a specific interval."""
	message = [x.lower() for x in message]
	target = message[0]
	amount = message[1]
	unit = message[2]
	reason = ' '.join(message[3:]).strip()
	if not reason:
		return "Please provide a valid reason."
	if not amount.isdigit():
		return "The amount must be a number."

	# Get target user ID
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)

	# Make sure the user exists
	if not targetUserID:
		return "{}: user not found".format(target)

	# Calculate silence seconds
	if unit == 's':
		silenceTime = int(amount)
	elif unit == 'm':
		silenceTime = int(amount) * 60
	elif unit == 'h':
		silenceTime = int(amount) * 3600
	elif unit == 'd':
		silenceTime = int(amount) * 86400
	else:
		return "Invalid time format (s/m/h/d)."

	# Max silence time is 7 days
	if silenceTime > 2.628e+6:
		return "Invalid silence time. Max silence time is 1 month."

	# Send silence packet to target if he's connected
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		# user online, silence both in db and with packet
		targetToken.silence(silenceTime, reason, userID)
	else:
		# User offline, silence user only in db
		userUtils.silence(targetUserID, silenceTime, reason, userID)

	# Log message
	msg = "{} has been silenced for: {}".format(target, reason)
	return msg

@registerCommand(trigger= "!removesilence", syntax= "<target>", privs= privileges.ADMIN_SILENCE_USERS)
def removeSilence(fro, chan, message):
	"""Unsilences a specific user."""
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	# Send new silence end packet to user if he's online
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		# User online, remove silence both in db and with packet
		targetToken.silence(0, "", userID)
	else:
		# user offline, remove islene ofnlt from db
		userUtils.silence(targetUserID, 0, "", userID)

	return "{}'s silence reset".format(target)

@registerCommand(trigger= "!ban", syntax= "<target>", privs= privileges.ADMIN_BAN_USERS)
def ban(fro, chan, message):
	"""Bans a specific user."""
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)
	if targetUserID in (999, 1000, 1001, 1002, 1005):
		return "NO!"
	# Set allowed to 0
	userUtils.ban(targetUserID)

	# Send ban packet to the user if he's online
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		targetToken.enqueue(serverPackets.loginBanned())

	log.rap(userID, "has banned {}".format(target), True)
	return "RIP {}. You will not be missed.".format(target)

@registerCommand(trigger= "!unban", syntax= "<target>", privs= privileges.ADMIN_BAN_USERS)
def unban(fro, chan, message):
	"""Unans a specific user."""
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	# Set allowed to 1
	userUtils.unban(targetUserID)

	log.rap(userID, "has unbanned {}".format(target), True)
	return "Welcome back {}!".format(target)

@registerCommand(trigger= "!restrict", syntax= "<target>", privs= privileges.ADMIN_BAN_USERS)
def restrict(fro, chan, message):
	"""Restricts a specific user."""
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)
	if targetUserID in (999, 1000):
		return "NO!"
		
	# Put this user in restricted mode
	userUtils.restrict(targetUserID)

	# Send restricted mode packet to this user if he's online
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		targetToken.setRestricted()

	log.rap(userID, "has put {} in restricted mode".format(target), True)
	return "Bye bye {}. See you later, maybe.".format(target)

@registerCommand(trigger= "!freeze", syntax= "<target>", privs= privileges.ADMIN_MANAGE_USERS)
def freeze(fro, chan, message):
	"""Freezes a specific user."""
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	# Get date & prepare freeze date
	now = datetime.now()
	freezedate = now + timedelta(days=2)
	freezedateunix = (freezedate-datetime(1970,1,1)).total_seconds()

	# Set freeze status & date
	glob.db.execute("UPDATE `users`  SET `frozen` = '1' WHERE `id` = '{}'".format(targetUserID))
	glob.db.execute("UPDATE `users`  SET `freezedate` = '{}' WHERE `id` = '{}'".format(freezedateunix, targetUserID))

	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		targetToken.enqueue(serverPackets.notification("You have been frozen! The RealistikOsu staff team has found you suspicious and would like to request a liveplay. Visit ussr.pl for more info."))

	log.rap(userID, "has frozen {}".format(target), True)
	return "User has been frozen!"

@registerCommand(trigger= "!unfreeze", syntax= "<target>", privs= privileges.ADMIN_MANAGE_USERS)
def unfreeze(fro, chan, message):
	"""Unfreezes a specific user."""
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	glob.db.execute("UPDATE `users`  SET `frozen` = '0' WHERE `id` = '{}'".format(targetUserID))
	glob.db.execute("UPDATE `users`  SET `freezedate` = '0' WHERE `id` = '{}'".format(targetUserID))
	glob.db.execute("UPDATE users  SET firstloginafterfrozen = '1' WHERE id = '{}'".format(targetUserID))
	#glob.db.execute(f"INSERT IGNORE INTO user_badges (user, badge) VALUES ({targetUserID}), 1005)")

	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken is not None:
		targetToken.enqueue(serverPackets.notification("Your account has been unfrozen! You have proven your legitemacy. Thank you and have fun playing on RealistikOsu!"))

	log.rap(userID, "has unfrozen {}".format(target), True)
	return "User has been unfrozen!"

@registerCommand(trigger= "!username", syntax= "<new username>", privs= privileges.USER_DONOR)
def changeUsername(fro, chan, message):
	"""Lets you change your username."""
	target = userUtils.safeUsername(fro)
	new = message[0]
	newl = message[0].lower()

	targetUserID = userUtils.getIDSafe(target)

	if not targetUserID:
		return "{}: User not found".format(target)

	tokens = glob.tokens.getTokenFromUserID(targetUserID, True)
	glob.db.execute("UPDATE `users`  SET `username` = %s, `username_safe` = %s WHERE `id` = %s", (new, newl, targetUserID))
	glob.db.execute("UPDATE `users_stats` SET `username` = %s WHERE `id` = %s", (new, targetUserID))
	glob.db.execute("UPDATE `rx_stats` SET `username` = %s WHERE `id` = %s", (new, targetUserID))
	glob.db.execute("UPDATE `ap_stats` SET `username` = %s WHERE `id` = %s", (new, targetUserID))
	tokens[0].kick("Your username has been changed to {}. Please relog!".format(new))

@registerCommand(trigger= "!unrestrict", syntax= "<target>", privs= privileges.ADMIN_BAN_USERS)
def unrestrict(fro, chan, message):
	"""Unrestricts a specific user."""
	# Get parameters
	for i in message:
		i = i.lower()
	target = message[0]

	# Make sure the user exists
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)
	if not targetUserID:
		return "{}: user not found".format(target)

	# Set allowed to 1
	userUtils.unrestrict(targetUserID)

	log.rap(userID, "has removed restricted mode from {}".format(target), True)
	return "Welcome back {}!".format(target)

@registerCommand(trigger= "!system restart", privs= privileges.ADMIN_MANAGE_SERVERS)
def systemRestart(fro, chan, message):
	return restartShutdown(True)

@registerCommand(trigger= "!system shutdown", privs= privileges.ADMIN_MANAGE_SERVERS)
def systemShutdown(fro, chan, message):
	return restartShutdown(False)

@registerCommand(trigger= "!system reload", privs= privileges.ADMIN_MANAGE_SERVERS)
def systemReload(fro, chan, message):
	glob.banchoConf.reload()
	return "Bancho settings reloaded!"

@registerCommand(trigger= "!system maintenance", privs= privileges.ADMIN_MANAGE_SERVERS)
def systemMaintenance(fro, chan, message):
	# Turn on/off bancho maintenance
	maintenance = True

	# Get on/off
	if len(message) >= 2:
		if message[1] == "off":
			maintenance = False

	# Set new maintenance value in bancho_settings table
	glob.banchoConf.setMaintenance(maintenance)

	if maintenance:
		# We have turned on maintenance mode
		# Users that will be disconnected
		who = []

		# Disconnect everyone but mod/admins
		with glob.tokens:
			for _, value in glob.tokens.tokens.items():
				if not value.admin:
					who.append(value.userID)

		glob.streams.broadcast("main", serverPackets.notification("Our realtime server is in maintenance mode. Please try to login again later."))
		glob.tokens.multipleEnqueue(serverPackets.loginError(), who)
		msg = "The server is now in maintenance mode!"
	else:
		# We have turned off maintenance mode
		# Send message if we have turned off maintenance mode
		msg = "The server is no longer in maintenance mode!"

	# Chat output
	return msg

@registerCommand(trigger= "!system status", privs= privileges.ADMIN_MANAGE_SERVERS)
def systemStatus(fro, chan, message):
	"""Shows the current server status."""
	# Fetch
	data = systemHelper.getSystemInfo()
	
	msg = "\n".join((
		"---> RealistikOsu <---",
		" - Realtime Server -",
		"> Running RealistikOsu pep.py fork.",
		f"> Online Users: {data['connectedUsers']}",
		f"> Multiplayer: {data['matches']}",
		f"> Uptime: {data['uptime']}",
		"",
		" - System Statistics -",
		f"> CPU Utilisation: {data['cpuUsage']}%",
		f"> RAM Utilisation: {data['usedMemory']}/{data['totalMemory']}",
		f"> CPU Utilisation History: {'%, '.join(data['loadAverage'])}"
	))

	return msg

@registerCommand(trigger= "\x01ACTION is playing")
@registerCommand(trigger= "\x01ACTION is listening to")
@registerCommand(trigger= "\x01ACTION is watching")
def tillerinoNp(fro, chan, message):
	"""Displays PP stats for a specific map."""
	try:
		# Mirror list trigger for #spect_
		if chan.startswith("#spect_"):
			spectatorHostUserID = getSpectatorHostUserIDFromChannel(chan)
			spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
			if spectatorHostToken is None:
				return False
			return mirrorMessage(spectatorHostToken.beatmapID)

		# Run the command in PM only
		if chan.startswith("#"):
			return False

		playWatch = message[1] == "playing" or message[1] == "watching"
		# Get URL from message
		if message[1] == "listening":
			beatmapURL = str(message[3][1:])
		elif playWatch:
			beatmapURL = str(message[2][1:])
		else:
			return False

		modsEnum = 0
		mapping = {
			"-Easy": mods.EASY,
			"-NoFail": mods.NOFAIL,
			"+Hidden": mods.HIDDEN,
			"+HardRock": mods.HARDROCK,
			"+Nightcore": mods.NIGHTCORE,
			"+DoubleTime": mods.DOUBLETIME,
			"-HalfTime": mods.HALFTIME,
			"+Flashlight": mods.FLASHLIGHT,
			"-SpunOut": mods.SPUNOUT
		}

		if playWatch:
			for part in message:
				part = part.replace("\x01", "")
				modsEnum += mapping.get(part, 0)

		# Reject regex. Return to monkey.
		beatmapID = beatmapURL.split("/")[-1]
		
		# Sneaky peppy!! Changing URL!
		if "#" in beatmapID:
			_, beatmapID = beatmapID.split("#")

		# Update latest tillerino song for current token
		token = glob.tokens.getTokenFromUsername(fro)
		if token is not None:
			token.tillerino = [int(beatmapID), modsEnum, -1.0]
		userID = token.userID

		# Return tillerino message
		return getPPMessage(userID)
	except:
		return False


def tillerinoMods(fro, chan, message):
	"""Displays the PP stats for a specific map with specific mods."""
	try:
		# Run the command in PM only
		if chan.startswith("#"):
			return False

		# Get token and user ID
		token = glob.tokens.getTokenFromUsername(fro)
		if token is None:
			return False
		userID = token.userID

		# Make sure the user has triggered the bot with /np command
		if token.tillerino[0] == 0:
			return "You must firstly select a beatmap using the /np command."

		# Check passed mods and convert to enum
		modsList = [message[0][i:i+2].upper() for i in range(0, len(message[0]), 2)]
		modsEnum = 0
		for i in modsList:
			if i not in ["NO", "NF", "EZ", "HD", "HR", "DT", "HT", "NC", "FL", "SO", "RX", "AP"]:
				return "Invalid mods. Allowed mods: NO, NF, EZ, HD, HR, DT, HT, NC, FL, SO, RX, AP. Do not use spaces for multiple mods."
			
			mods = {
				"NO": 0,
				"NF": mods.NOFAIL,
				"EZ": mods.EASY,
				"HD": mods.HIDDEN,
				"HR": mods.HARDROCK,
				"DT": mods.DOUBLETIME,
				"HT": mods.HALFTIME,
				"NC": mods.NIGHTCORE,
				"FL": mods.FLASHLIGHT,
				"SO": mods.SPUNOUT,
				"RX": mods.RELAX,
				"AP": mods.RELAX2
			}.get(i, 0)

			modsEnum += mods
			if mods == 0:
				break

		# Set mods
		token.tillerino[1] = modsEnum

		# Return tillerino message for that beatmap with mods
		return getPPMessage(userID)
	except:
		return False

@registerCommand(trigger= "!acc", syntax= "<accuracy>")
def tillerinoAcc(fro, chan, message):
	"""Displays the PP stats for a specific map with a specific accuracy."""
	try:
		# Run the command in PM only
		if chan.startswith("#"):
			return False

		# Get token and user ID
		token = glob.tokens.getTokenFromUsername(fro)
		if token is None:
			return False
		userID = token.userID

		# Make sure the user has triggered the bot with /np command
		if token.tillerino[0] == 0:
			return "You must firstly select a beatmap using the /np command."

		# Convert acc to float
		acc = float(message[0])

		# Set new tillerino list acc value
		token.tillerino[2] = acc

		# Return tillerino message for that beatmap with mods
		return getPPMessage(userID)
	except ValueError:
		return "Invalid acc value"
	except:
		return False

@registerCommand(trigger= "!last")
def tillerinoLast(fro, chan, message):
	try:
		# Run the command in PM only
		if chan.startswith("#"):
			return False

		data = glob.db.fetch("""SELECT beatmaps.song_name as sn, scores.*,
			beatmaps.beatmap_id as bid, beatmaps.difficulty_std, beatmaps.difficulty_taiko, beatmaps.difficulty_ctb, beatmaps.difficulty_mania, beatmaps.max_combo as fc
		FROM scores
		LEFT JOIN beatmaps ON beatmaps.beatmap_md5=scores.beatmap_md5
		LEFT JOIN users ON users.id = scores.userid
		WHERE users.username = %s
		ORDER BY scores.time DESC
		LIMIT 1""", [fro])
		if data is None:
			return False

		diffString = "difficulty_{}".format(gameModes.getGameModeForDB(data["play_mode"]))
		rank = generalUtils.getRank(data["play_mode"], data["mods"], data["accuracy"],
									data["300_count"], data["100_count"], data["50_count"], data["misses_count"])

		ifPlayer = "{0} | ".format(fro) if chan != glob.BOT_NAME else ""
		ifFc = " (FC)" if data["max_combo"] == data["fc"] else " {0}x/{1}x".format(data["max_combo"], data["fc"])
		beatmapLink = "[http://osu.ppy.sh/b/{1} {0}]".format(data["sn"], data["bid"])

		hasPP = data["play_mode"] != gameModes.CTB

		msg = ifPlayer
		msg += beatmapLink
		if data["play_mode"] != gameModes.STD:
			msg += " <{0}>".format(gameModes.getGameModeForPrinting(data["play_mode"]))

		if data["mods"]:
			msg += ' +' + generalUtils.readableMods(data["mods"])

		if not hasPP:
			msg += " | {0:,}".format(data["score"])
			msg += ifFc
			msg += " | {0:.2f}%, {1}".format(data["accuracy"], rank.upper())
			msg += " {{ {0} / {1} / {2} / {3} }}".format(data["300_count"], data["100_count"], data["50_count"], data["misses_count"])
			msg += " | {0:.2f} stars".format(data[diffString])
			return msg

		msg += " ({0:.2f}%, {1})".format(data["accuracy"], rank.upper())
		msg += ifFc
		msg += " | {0:.2f}pp".format(data["pp"])

		stars = data[diffString]
		if data["mods"]:
			token = glob.tokens.getTokenFromUsername(fro)
			if token is None:
				return False
			userID = token.userID
			token.tillerino[0] = data["bid"]
			token.tillerino[1] = data["mods"]
			token.tillerino[2] = data["accuracy"]
			oppaiData = getPPMessage(userID, just_data=True)
			if "stars" in oppaiData:
				stars = oppaiData["stars"]

		msg += " | {0:.2f} stars".format(stars)
		return msg
	except Exception as a:
		log.error(a)
		return False

@registerCommand(trigger= "!pp")
def pp(fro, chan, message):
	if chan.startswith("#"):
		return False

	gameMode = None
	if len(message) >= 1:
		gm = {
			"standard": 0,
			"std": 0,
			"taiko": 1,
			"ctb": 2,
			"mania": 3
		}
		if message[0].lower() not in gm:
			return "What's that game mode? I've never heard of it :/"
		else:
			gameMode = gm[message[0].lower()]

	token = glob.tokens.getTokenFromUsername(fro)
	if token is None:
		return False
	if gameMode is None:
		gameMode = token.gameMode
	if gameMode == gameModes.TAIKO or gameMode == gameModes.CTB:
		return "PP for your current game mode is not supported yet."
	pp = userUtils.getPP(token.userID, gameMode)
	return "You have {:,} pp".format(pp)

@registerCommand(trigger= "!report")
def report(fro, chan, message):
	"""Reports a specific user."""
	msg = ""
	try:
		# TODO: Rate limit
		# Regex on message
		reportRegex = re.compile("^(.+) \((.+)\)\:(?: )?(.+)?$")
		result = reportRegex.search(" ".join(message))

		# Make sure the message matches the regex
		if result is None:
			raise exceptions.invalidArgumentsException()

		# Get username, report reason and report info
		target, reason, additionalInfo = result.groups()
		target = chat.fixUsernameForBancho(target)

		# Make sure the target is not foka
		if target.lower() == glob.BOT_NAME.lower():
			raise exceptions.invalidUserException()

		# Make sure the user exists
		targetID = userUtils.getID(target)
		if targetID == 0:
			raise exceptions.userNotFoundException()

		# Make sure that the user has specified additional info if report reason is 'Other'
		if reason.lower() == "other" and additionalInfo is None:
			raise exceptions.missingReportInfoException()

		# Get the token if possible
		chatlog = ""
		token = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
		if token is not None:
			chatlog = token.getMessagesBufferString()

		# Everything is fine, submit report
		glob.db.execute("INSERT INTO reports (id, from_uid, to_uid, reason, chatlog, time) VALUES (NULL, %s, %s, %s, %s, %s)", [userUtils.getID(fro), targetID, "{reason} - ingame {info}".format(reason=reason, info="({})".format(additionalInfo) if additionalInfo is not None else ""), chatlog, int(time.time())])
		msg = "You've reported {target} for {reason}{info}. A Community Manager will check your report as soon as possible. Every !report message you may see in chat wasn't sent to anyone, so nobody in chat, but admins, know about your report. Thank you for reporting!".format(target=target, reason=reason, info="" if additionalInfo is None else " (" + additionalInfo + ")")
		adminMsg = "{user} has reported {target} for {reason} ({info})".format(user=fro, target=target, reason=reason, info=additionalInfo)

		# Log report in #admin and on discord
		chat.sendMessage(glob.BOT_NAME, "#admin", adminMsg)
		log.warning(adminMsg, discord="cm")
	except exceptions.invalidUserException:
		msg = "Hello, {} here! You can't report me. I won't forget what you've tried to do. Watch out.".format(glob.BOT_NAME)
	except exceptions.invalidArgumentsException:
		msg = "Invalid report command syntax. To report an user, click on it and select 'Report user'."
	except exceptions.userNotFoundException:
		msg = "The user you've tried to report doesn't exist."
	except exceptions.missingReportInfoException:
		msg = "Please specify the reason of your report."
	except:
		raise
	finally:
		if msg != "":
			token = glob.tokens.getTokenFromUsername(fro)
			if token is not None:
				if token.irc:
					chat.sendMessage(glob.BOT_NAME, fro, msg)
				else:
					token.enqueue(serverPackets.notification(msg))
	return False

@registerCommand(trigger= "!mp", syntax= "<subcommand>", privs= privileges.USER_TOURNAMENT_STAFF)
def multiplayer(fro, chan, message):
	"""All the multiplayer subcommands."""
	def mpMake():
		if len(message) < 2:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp make <name>")
		matchName = " ".join(message[1:]).strip()
		if not matchName:
			raise exceptions.invalidArgumentsException("Match name must not be empty!")
		matchID = glob.matches.createMatch(matchName, generalUtils.stringMd5(generalUtils.randomString(32)), 0, "Tournament", "", 0, -1, isTourney=True)
		glob.matches.matches[matchID].sendUpdates()
		return "Tourney match #{} created!".format(matchID)

	def mpJoin():
		if len(message) < 2 or not message[1].isdigit():
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp join <id>")
		matchID = int(message[1])
		userToken = glob.tokens.getTokenFromUsername(fro, ignoreIRC=True)
		if userToken is None:
			raise exceptions.invalidArgumentsException(
				"No game clients found for {}, can't join the match. "
			    "If you're a referee and you want to join the chat "
				"channel from IRC, use /join #multi_{} instead.".format(fro, matchID)
			)
		userToken.joinMatch(matchID)
		return "Attempting to join match #{}!".format(matchID)

	def mpClose():
		matchID = getMatchIDFromChannel(chan)
		glob.matches.disposeMatch(matchID)
		return "Multiplayer match #{} disposed successfully".format(matchID)

	def mpLock():
		matchID = getMatchIDFromChannel(chan)
		glob.matches.matches[matchID].isLocked = True
		return "This match has been locked"

	def mpUnlock():
		matchID = getMatchIDFromChannel(chan)
		glob.matches.matches[matchID].isLocked = False
		return "This match has been unlocked"

	def mpSize():
		if len(message) < 2 or not message[1].isdigit() or int(message[1]) < 2 or int(message[1]) > 16:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp size <slots(2-16)>")
		matchSize = int(message[1])
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.forceSize(matchSize)
		return "Match size changed to {}".format(matchSize)

	def mpMove():
		if len(message) < 3 or not message[2].isdigit() or int(message[2]) < 0 or int(message[2]) > 16:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp move <username> <slot>")
		username = message[1]
		newSlotID = int(message[2])
		userID = userUtils.getIDSafe(username)
		if userID is None:
			raise exceptions.userNotFoundException("No such user")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		success = _match.userChangeSlot(userID, newSlotID)
		if success:
			result = "Player {} moved to slot {}".format(username, newSlotID)
		else:
			result = "You can't use that slot: it's either already occupied by someone else or locked"
		return result

	def mpHost():
		if len(message) < 2:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp host <username>")
		username = message[1].strip()
		if not username:
			raise exceptions.invalidArgumentsException("Please provide a username")
		userID = userUtils.getIDSafe(username)
		if userID is None:
			raise exceptions.userNotFoundException("No such user")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		success = _match.setHost(userID)
		return "{} is now the host".format(username) if success else "Couldn't give host to {}".format(username)

	def mpClearHost():
		matchID = getMatchIDFromChannel(chan)
		glob.matches.matches[matchID].removeHost()
		return "Host has been removed from this match"

	def mpStart():
		def _start():
			matchID = getMatchIDFromChannel(chan)
			success = glob.matches.matches[matchID].start()
			if not success:
				chat.sendMessage(glob.BOT_NAME, chan, "Couldn't start match. Make sure there are enough players and "
												  "teams are valid. The match has been unlocked.")
			else:
				chat.sendMessage(glob.BOT_NAME, chan, "Have fun!")


		def _decreaseTimer(t):
			if t <= 0:
				_start()
			else:
				if t % 10 == 0 or t <= 5:
					chat.sendMessage(glob.BOT_NAME, chan, "Match starts in {} seconds.".format(t))
				threading.Timer(1.00, _decreaseTimer, [t - 1]).start()

		if len(message) < 2 or not message[1].isdigit():
			startTime = 0
		else:
			startTime = int(message[1])

		force = False if len(message) < 3 else message[2].lower() == "force"
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]

		# Force everyone to ready
		someoneNotReady = False
		for i, slot in enumerate(_match.slots):
			if slot.status != slotStatuses.READY and slot.user is not None:
				someoneNotReady = True
				if force:
					_match.toggleSlotReady(i)

		if someoneNotReady and not force:
			return "Some users aren't ready yet. Use '!mp start force' if you want to start the match, " \
				   "even with non-ready players."

		if startTime == 0:
			_start()
			return "Starting match"
		else:
			_match.isStarting = True
			threading.Timer(1.00, _decreaseTimer, [startTime - 1]).start()
			return "Match starts in {} seconds. The match has been locked. " \
				   "Please don't leave the match during the countdown " \
				   "or you might receive a penalty.".format(startTime)

	def mpInvite():
		if len(message) < 2:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp invite <username>")
		username = message[1].strip()
		if not username:
			raise exceptions.invalidArgumentsException("Please provide a username")
		userID = userUtils.getIDSafe(username)
		if userID is None:
			raise exceptions.userNotFoundException("No such user")
		token = glob.tokens.getTokenFromUserID(userID, ignoreIRC=True)
		if token is None:
			raise exceptions.invalidUserException("That user is not connected to bancho right now.")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.invite(999, userID)
		token.enqueue(serverPackets.notification("Please accept the invite you've just received from {} to "
												 "enter your tourney match.".format(glob.BOT_NAME)))
		return "An invite to this match has been sent to {}".format(username)

	def mpMap():
		if len(message) < 2 or not message[1].isdigit() or (len(message) == 3 and not message[2].isdigit()):
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp map <beatmapid> [<gamemode>]")
		beatmapID = int(message[1])
		gameMode = int(message[2]) if len(message) == 3 else 0
		if gameMode < 0 or gameMode > 3:
			raise exceptions.invalidArgumentsException("Gamemode must be 0, 1, 2 or 3")
		beatmapData = glob.db.fetch("SELECT * FROM beatmaps WHERE beatmap_id = %s LIMIT 1", [beatmapID])
		if beatmapData is None:
			raise exceptions.invalidArgumentsException("The beatmap you've selected couldn't be found in the database."
													   "If the beatmap id is valid, please load the scoreboard first in "
													   "order to cache it, then try again.")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.beatmapID = beatmapID
		_match.beatmapName = beatmapData["song_name"]
		_match.beatmapMD5 = beatmapData["beatmap_md5"]
		_match.gameMode = gameMode
		_match.resetReady()
		_match.sendUpdates()
		return "Match map has been updated"

	def mpSet():
		if len(message) < 2 or not message[1].isdigit() or \
				(len(message) >= 3 and not message[2].isdigit()) or \
				(len(message) >= 4 and not message[3].isdigit()):
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp set <teammode> [<scoremode>] [<size>]")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		matchTeamType = int(message[1])
		matchScoringType = int(message[2]) if len(message) >= 3 else _match.matchScoringType
		if not 0 <= matchTeamType <= 3:
			raise exceptions.invalidArgumentsException("Match team type must be between 0 and 3")
		if not 0 <= matchScoringType <= 3:
			raise exceptions.invalidArgumentsException("Match scoring type must be between 0 and 3")
		oldMatchTeamType = _match.matchTeamType
		_match.matchTeamType = matchTeamType
		_match.matchScoringType = matchScoringType
		if len(message) >= 4:
			_match.forceSize(int(message[3]))
		if _match.matchTeamType != oldMatchTeamType:
			_match.initializeTeams()
		if _match.matchTeamType == matchTeamTypes.TAG_COOP or _match.matchTeamType == matchTeamTypes.TAG_TEAM_VS:
			_match.matchModMode = matchModModes.NORMAL

		_match.sendUpdates()
		return "Match settings have been updated!"

	def mpAbort():
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.abort()
		return "Match aborted!"

	def mpKick():
		if len(message) < 2:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp kick <username>")
		username = message[1].strip()
		if not username:
			raise exceptions.invalidArgumentsException("Please provide a username")
		userID = userUtils.getIDSafe(username)
		if userID is None:
			raise exceptions.userNotFoundException("No such user")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		slotID = _match.getUserSlotID(userID)
		if slotID is None:
			raise exceptions.userNotFoundException("The specified user is not in this match")
		for i in range(0, 2):
			_match.toggleSlotLocked(slotID)
		return "{} has been kicked from the match.".format(username)

	def mpPassword():
		password = "" if len(message) < 2 or not message[1].strip() else message[1]
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.changePassword(password)
		return "Match password has been changed!"

	def mpRandomPassword():
		password = generalUtils.stringMd5(generalUtils.randomString(32))
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.changePassword(password)
		return "Match password has been changed to a random one"

	def mpMods():
		if len(message) < 2:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp <mod1> [<mod2>] ...")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		newMods = 0
		freeMod = False
		for _mod in message[1:]:
			if _mod.lower().strip() == "hd":
				newMods |= mods.HIDDEN
			elif _mod.lower().strip() == "hr":
				newMods |= mods.HARDROCK
			elif _mod.lower().strip() == "dt":
				newMods |= mods.DOUBLETIME
			elif _mod.lower().strip() == "fl":
				newMods |= mods.FLASHLIGHT
			elif _mod.lower().strip() == "fi":
				newMods |= mods.FADEIN
			elif _mod.lower().strip() == "ez":
				newMods |= mods.EASY
			if _mod.lower().strip() == "none":
				newMods = 0

			if _mod.lower().strip() == "freemod":
				freeMod = True

		_match.matchModMode = matchModModes.FREE_MOD if freeMod else matchModModes.NORMAL
		_match.resetReady()
		if _match.matchModMode == matchModModes.FREE_MOD:
			_match.resetMods()
		_match.changeMods(newMods)
		return "Match mods have been updated!"

	def mpTeam():
		if len(message) < 3:
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp team <username> <colour>")
		username = message[1].strip()
		if not username:
			raise exceptions.invalidArgumentsException("Please provide a username")
		colour = message[2].lower().strip()
		if colour not in ["red", "blue"]:
			raise exceptions.invalidArgumentsException("Team colour must be red or blue")
		userID = userUtils.getIDSafe(username)
		if userID is None:
			raise exceptions.userNotFoundException("No such user")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.changeTeam(userID, matchTeams.BLUE if colour == "blue" else matchTeams.RED)
		return "{} is now in {} team".format(username, colour)

	def mpSettings():
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		single = False if len(message) < 2 else message[1].strip().lower() == "single"
		msg = "PLAYERS IN THIS MATCH "
		if not single:
			msg += "(use !mp settings single for a single-line version):"
			msg += "\n"
		else:
			msg += ": "
		empty = True
		for slot in _match.slots:
			if slot.user is None:
				continue
			readableStatuses = {
				slotStatuses.READY: "ready",
				slotStatuses.NOT_READY: "not ready",
				slotStatuses.NO_MAP: "no map",
				slotStatuses.PLAYING: "playing",
			}
			if slot.status not in readableStatuses:
				readableStatus = "???"
			else:
				readableStatus = readableStatuses[slot.status]
			empty = False
			msg += "* [{team}] <{status}> ~ {username}{mods}{nl}".format(
				team="red" if slot.team == matchTeams.RED else "blue" if slot.team == matchTeams.BLUE else "!! no team !!",
				status=readableStatus,
				username=glob.tokens.tokens[slot.user].username,
				mods=" (+ {})".format(generalUtils.readableMods(slot.mods)) if slot.mods > 0 else "",
				nl=" | " if single else "\n"
			)
		if empty:
			msg += "Nobody.\n"
		msg = msg.rstrip(" | " if single else "\n")
		return msg

	def mpScoreV():
		if len(message) < 2 or message[1] not in ("1", "2"):
			raise exceptions.invalidArgumentsException("Wrong syntax: !mp scorev <1|2>")
		_match = glob.matches.matches[getMatchIDFromChannel(chan)]
		_match.matchScoringType = matchScoringTypes.SCORE_V2 if message[1] == "2" else matchScoringTypes.SCORE
		_match.sendUpdates()
		return "Match scoring type set to scorev{}".format(message[1])

	def mpHelp():
		return "Supported subcommands: !mp <{}>".format("|".join(k for k in subcommands.keys()))

	try:
		subcommands = {
			"make": mpMake,
			"close": mpClose,
			"join": mpJoin,
			"lock": mpLock,
			"unlock": mpUnlock,
			"size": mpSize,
			"move": mpMove,
			"host": mpHost,
			"clearhost": mpClearHost,
			"start": mpStart,
			"invite": mpInvite,
			"map": mpMap,
			"set": mpSet,
			"abort": mpAbort,
			"kick": mpKick,
			"password": mpPassword,
			"randompassword": mpRandomPassword,
			"mods": mpMods,
			"team": mpTeam,
			"settings": mpSettings,
            "scorev": mpScoreV,
			"help": mpHelp
		}
		requestedSubcommand = message[0].lower().strip()
		if requestedSubcommand not in subcommands:
			raise exceptions.invalidArgumentsException("Invalid subcommand")
		return subcommands[requestedSubcommand]()
	except (exceptions.invalidArgumentsException, exceptions.userNotFoundException, exceptions.invalidUserException) as e:
		return str(e)
	except exceptions.wrongChannelException:
		return "This command only works in multiplayer chat channels"
	except exceptions.matchNotFoundException:
		return "Match not found"
	except:
		raise

@registerCommand(trigger= "!switchserver", syntax= "<server_url>", privs= privileges.ADMIN_MANAGE_SERVERS)
def switchServer(fro, chan, message):
	# Get target user ID
	target = message[0]
	newServer = message[1].strip()
	if not newServer:
		return "Invalid server IP"
	targetUserID = userUtils.getIDSafe(target)
	userID = userUtils.getID(fro)

	# Make sure the user exists
	if not targetUserID:
		return "{}: user not found".format(target)

	# Connect the user to the end server
	userToken = glob.tokens.getTokenFromUserID(userID, ignoreIRC=True, _all=False)
	userToken.enqueue(serverPackets.switchServer(newServer))

	# Disconnect the user from the origin server
	# userToken.kick()
	return "{} has been connected to {}".format(target, newServer)

@registerCommand(trigger= "!announce", syntax= "<announcement>", privs= privileges.ADMIN_SEND_ALERTS)
def postAnnouncement(fro, chan, message): # Post to #announce ingame
	announcement = ' '.join(message[0:])
	chat.sendMessage(glob.BOT_NAME, "#announce", announcement)
	return "Announcement successfully sent."

@registerCommand(trigger= "!chimu")
def chimu(fro, chan, message):
	"""Gets a download URL for the beatmap from Chimu."""
	try:
		matchID = getMatchIDFromChannel(chan)
	except exceptions.wrongChannelException:
		matchID = None
	try:
		spectatorHostUserID = getSpectatorHostUserIDFromChannel(chan)
	except exceptions.wrongChannelException:
		spectatorHostUserID = None

	if matchID is not None:
		if matchID not in glob.matches.matches:
			return "This match doesn't seem to exist... Or does it...?"
		beatmapID = glob.matches.matches[matchID].beatmapID
	else:
		spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
		if spectatorHostToken is None:
			return "The spectator host is offline."
		beatmapID = spectatorHostToken.beatmapID
	return chimuMessage(beatmapID)

@registerCommand(trigger= "!beatconnect")
def beatconnect(fro, chan, message):
	"""Gets a download URL for the beatmap from Beatconnect."""
	try:
		matchID = getMatchIDFromChannel(chan)
	except exceptions.wrongChannelException:
		matchID = None
	try:
		spectatorHostUserID = getSpectatorHostUserIDFromChannel(chan)
	except exceptions.wrongChannelException:
		spectatorHostUserID = None

	if matchID is not None:
		if matchID not in glob.matches.matches:
			return "This match doesn't seem to exist... Or does it...?"
		beatmapID = glob.matches.matches[matchID].beatmapID
	else:
		spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
		if spectatorHostToken is None:
			return "The spectator host is offline."
		beatmapID = spectatorHostToken.beatmapID
	return beatconnectMessage(beatmapID)

@registerCommand(trigger= "!mirror")
def mirror(fro, chan, message):
	try:
		matchID = getMatchIDFromChannel(chan)
	except exceptions.wrongChannelException:
		matchID = None
	try:
		spectatorHostUserID = getSpectatorHostUserIDFromChannel(chan)
	except exceptions.wrongChannelException:
		spectatorHostUserID = None

	if matchID is not None:
		if matchID not in glob.matches.matches:
			return "This match doesn't seem to exist... Or does it...?"
		beatmapID = glob.matches.matches[matchID].beatmapID
	else:
		spectatorHostToken = glob.tokens.getTokenFromUserID(spectatorHostUserID, ignoreIRC=True)
		if spectatorHostToken is None:
			return "The spectator host is offline."
		beatmapID = spectatorHostToken.beatmapID
	return mirrorMessage(beatmapID)

@registerCommand(trigger= "!crash", syntax= "<target>", privs= privileges.ADMIN_MANAGE_USERS)
def crashuser(fro, chan, message):
	"""Crashes the persons game lmfao"""
	#talnacialex found this he is good lad
	for i in message:
		i = i.lower()
	target = message[0]
	targetToken = glob.tokens.getTokenFromUsername(userUtils.safeUsername(target), safe=True)
	if targetToken == None:
		#bruh they dont exist
		return "bruh they literally dont exist"
	targetToken.enqueue(serverPackets.crash())
	return ":^)"

@registerCommand(trigger= "!bless", syntax= "<target>", privs= privileges.ADMIN_MANAGE_USERS)
def bless(fro: str, chan: str, message: str) -> str:
	"""Blesses them with the holy texts, and then proceeds to crash their game
	because the bible is chonky. Oh yeah this is also expensive CPU, Memory wise
	as there is a lot of packet writing and massive str."""

	target = userUtils.safeUsername(message[0])
	t_user = glob.tokens.getTokenFromUsername(target, safe=True)
	if not t_user: return "This user is not online, and may not be blessed."

	# Acquire bible from web so we dont store it in mem for too long.
	try:
		holy_bible = requests.get("http://jesus.tsunyoku.xyz/files/10/10-0.txt").text
	except Exception as e:
		return f"THE SACRED TEXTS COULD NOT BE ACQUIRED DUE TO THE DEVIL INTRODUCING ERROR {e}!!!"
	
	# Split the bible into 2000 char chunks (str writer and reader limit)
	bible_split = [holy_bible [i:i+2000] for i in range(0, len(holy_bible), 2000)]
	
	# Use bytearray for speed
	q = bytearray()
	for b in bible_split:
		q += serverPackets.sendMessage("Jesus", t_user.username, b)
	t_user.enqueue(q)
	return "THEY ARE BLESSED AND ASCENDED TO HeAVeN"

@registerCommand(trigger= "!help")
def help_cmd(fro, chan, message):
	"""Lists all currently available commands!"""

	help_cmd = f"List of all currently available commands on RealistikOsu! ({len(commands)} total)\n"

	for command in commands:
		# Basic checks.
		if command["trigger"][0] != "!": continue

		# Make sure callback docstring is not none
		docstr = command.get("callback").__doc__ # Miss you walrus
		if docstr is None: docstr = "No description available."

		name = command["trigger"]
		if command.get("syntax"): name += f" {command['syntax']}"

		help_cmd += f" - {name} - {docstr}\n"
	
	return help_cmd