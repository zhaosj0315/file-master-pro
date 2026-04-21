# setup_minimal.py
from setuptools import setup
import sys

APP_NAME = "File Master Pro"
APP_SCRIPT = "main.py"

# Increase recursion limit
sys.setrecursionlimit(15000)

OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'app_icon.icns',
    'packages': ['send2trash', 'ttkthemes', 'PyQt5'],
    'includes': ['PIL.Image', 'PIL.ImageTk'],
    'excludes': [
        'numpy', 'scipy', 'matplotlib', 'pandas', 'sklearn', 'tensorflow',
        'torch', 'torchvision', 'torchaudio', 'transformers', 'jax',
        'jupyter', 'ipython', 'notebook', 'qtconsole', 'spyder',
        'tkinter.test', 'test', 'tests',
        'distutils', 'setuptools', 'pip', 'wheel'
    ],
    'optimize': 1,
    'no_chdir': True,
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': "A powerful file management and cleaning utility",
        'CFBundleIdentifier': "com.yourdomain.filemasterpro",
        'CFBundleVersion': "2.0.0",
        'CFBundleShortVersionString': "2.0",
        'NSHumanReadableCopyright': 'Copyright © 2025 Your Name. All rights reserved.'
    }
}

setup(
    app=[APP_SCRIPT],
    name=APP_NAME,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
