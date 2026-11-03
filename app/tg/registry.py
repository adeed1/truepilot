"""Every command and button lives in its own small file under commands/. This file just collects them."""
import importlib
import pkgutil

COMMANDS = {}   # "status" -> Command
CALLBACKS = {}  # "a" -> (function, level)

# levels: "safe" = only shows things, "act" = does one small thing (start an app, wake a PC),
#         "power" = the powerful group (needs the Powerful commands switch)
#         "approve" = answering a request that is waiting for your approval (needs the Approval requests switch)


class Command:
    def __init__(self, name, desc, level, fn, menu, args):
        self.name, self.desc, self.level, self.fn, self.menu, self.args = name, desc, level, fn, menu, args


def command(name, desc, level="safe", menu=True, args=""):
    def deco(fn):
        COMMANDS[name] = Command(name, desc, level, fn, menu, args)
        return fn
    return deco


def callback(prefix, level="safe"):
    def deco(fn):
        CALLBACKS[prefix] = (fn, level)
        return fn
    return deco


def load():
    from . import commands
    for m in pkgutil.iter_modules(commands.__path__):
        if not m.name.startswith("_"):
            importlib.import_module(f"{commands.__name__}.{m.name}")
