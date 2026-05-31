# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for WAC Huawei LLDP Crawl Data (PySide6 GUI)
# Build command: pyinstaller build/build.spec --distpath dist --workpath build/temp

import os
import sys

block_cipher = None

# Project root is one level up from this spec file
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'main.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[
        'gui',
        'gui.main_window',
        'gui.login_page',
        'gui.crawl_page',
        'gui.workers',
        'gui.config_store',
        'gui.encryption',
        'gui.themes',
        'gui.validators',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused PySide6/Qt modules to reduce output size (target 60-80 MB)
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DAnimation',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQml',
        'PySide6.QtQmlModels',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtTest',
        # Also exclude other heavy unused modules
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPositioning',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtSql',
        'PySide6.QtSvgWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtXml',
        # Exclude libraries not needed at runtime
        'pytest',
        'hypothesis',
        'pytest_qt',
        'pytest_mock',
        'tqdm',
        'rich',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WAC-Crawl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WAC-Crawl',
)
