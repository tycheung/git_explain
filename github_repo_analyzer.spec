# WIP this file does not work properly

# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for GitHub Repository Analyzer.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# Add debug flag for additional output
debug_enabled = True
console_enabled = True  # Set to True to see console output for debugging

# Current directory for relative paths (using getcwd instead of __file__)
current_dir = os.getcwd()

# Make sure the paths to assets are correct
src_dir = os.path.join(current_dir, 'src')
ui_templates = os.path.join(src_dir, 'ui', 'templates')
ui_static = os.path.join(src_dir, 'ui', 'static')

# Collect hidden imports
hidden_imports = collect_submodules('llama_cpp') + \
                 collect_submodules('transformers') + \
                 collect_submodules('huggingface_hub') + \
                 collect_submodules('torch') + \
                 collect_submodules('numpy') + \
                 collect_submodules('faiss') + \
                 collect_submodules('flask') + \
                 collect_submodules('requests') + \
                 collect_submodules('httpx') + \
                 collect_submodules('ast') + \
                 collect_submodules('re') + \
                 collect_submodules('werkzeug') + \
                 collect_submodules('jinja2') + \
                 collect_submodules('engineio.async_drivers.threading') + \
                 collect_submodules('engineio.async_drivers.eventlet') + \
                 collect_submodules('flask.templating') + \
                 collect_submodules('threading') + \
                 collect_submodules('webbrowser')

# Add the main application modules
hidden_imports += [
    'src',
    'src.config',
    'src.github.repo',
    'src.indexer.parser',
    'src.indexer.vectorizer',
    'src.indexer.structure',
    'src.indexer.dependencies',
    'src.indexer.incremental',
    'src.retriever.faiss_index',
    'src.retriever.hybrid_search',
    'src.generator.llm',
    'src.generator.code_generator',
    'src.utils.progress'
]

# Collect data files
datas = collect_data_files('transformers', include_py_files=True)
datas += collect_data_files('sentence_transformers', include_py_files=True)

# Make sure UI assets are explicitly included with correct paths
datas += [(ui_templates, 'ui/templates')]
datas += [(ui_static, 'ui/static')]

# Add any additional Python files that might need to be explicitly included
a = Analysis(
    ['src/main.py'],  # Changed to use main.py as entry point
    pathex=[current_dir, src_dir],  # Add both current and src directories to path
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],  # Empty list here means no console output will be captured
    exclude_binaries=True,  # Separate the binaries from the EXE
    name='github-repo-analyzer',
    debug=debug_enabled,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console_enabled,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(src_dir, 'ui', 'static', 'img', 'icon.ico') if os.path.exists(os.path.join(src_dir, 'ui', 'static', 'img', 'icon.ico')) else None,
)

# Create the COLLECT stage for all binaries and data files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='github-repo-analyzer',
)