from esky import bdist_esky
from glob import glob
from distutils.core import setup
from agility import VERSION
import platform

includes = ["sqlite3", "elementtree", "wx.lib.pubsub.core.*","wx.lib.pubsub.core.kwargs.listenerimpl","wx.lib.pubsub.core.kwargs.*", "wx.lib.wordwrap"]

if platform.system() == "Windows":
  includes.extend(["win32print", "win32api"])

setup(name="agi",
    version=VERSION,
    scripts=["agility.pyw"],
    data_files=["agility.xrc", ("images", glob("images/*")), "default.db", ("fonts", glob("fonts/*"))],
    options={"bdist_esky":{"freezer_module":"bbfreeze","bundle_msvcrt":True, "includes":includes}}
    )

