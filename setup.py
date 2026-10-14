"""Build LMemM.app (macOS):  ./build_app.sh   (alias build, uses this repo and its data/)

LSUIElement keeps it out of the Dock: LMemM lives in the menu bar and as the pill.
Permissions (Screen Recording, Accessibility, Input Monitoring, Microphone) are granted to
LMemM.app itself, not to the terminal it happens to be started from.
"""
from setuptools import setup

OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "LMemM",
        "CFBundleDisplayName": "LMemM",
        "CFBundleIdentifier": "com.adityakhuntia.lmemm",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,
        "LSEnvironment": {"PYTHONUTF8": "1", "LANG": "en_US.UTF-8"},   # an app has no shell locale: files would read as ASCII
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "LMemM listens when you press the note shortcut.",
        "NSSpeechRecognitionUsageDescription": "LMemM turns your spoken note into text on this Mac.",
        "NSAppleEventsUsageDescription": "LMemM reads the address of the browser tab you are on.",
    },
}

setup(app=["packaging/app_main.py"], options={"py2app": OPTIONS}, setup_requires=["py2app"])
