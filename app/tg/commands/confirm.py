"""Buttons on the 'Are you sure?' questions that your own commands ask."""
import time

from ..registry import callback
from ..ui import B, Screen


@callback("cy", "act")
async def yes(call):
    ent = call.eng.confirms.pop(call.data[0], None)
    if not ent or ent["exp"] < time.time() or ent["bot"] != call.bot["id"]:
        return Screen("That question has expired or was already answered. Ask again if you still want it.", [[B("« Menu", "m")]])
    call.tp.audit("Telegram", 0, "telegram_approved", "button", "Approve tapped")
    return await ent["run"]()


@callback("cn", "act")
async def no(call):
    call.eng.confirms.pop(call.data[0], None)
    return Screen("❌ Denied. Nothing was changed.", [[B("« Menu", "m")]])
