# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Gamepad Manager
Run with: pyinstaller main.spec
"""

a = Analysis(
    ['main.py', 'plat/windows.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('controller.png', '.'),  # Include the icon file
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'hidapi',
        'ctypes',
        'controllers.detector',
        'controllers.batteryprovider',
        'models.controller',
        'plat.windows',
        'tray.tray_icon',
        'workers.poller',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GamepadManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # No console window for tray app
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='controller.png',  # Application icon
)
