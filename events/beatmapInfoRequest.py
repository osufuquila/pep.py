from objects.osuToken import UserToken
from helpers.user_helper import restrict_with_log

def handle(token: UserToken, _) -> None:
    restrict_with_log(
        token.userID,
        "Outdated client bypassing login gate",
        "The user has send a beatmap request packet, which has been removed "
        "since ~2020. This means that they likely have a client with a version "
        "changer to bypass the login gate. (bancho gate)"
    )
