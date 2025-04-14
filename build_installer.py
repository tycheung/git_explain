#!/usr/bin/env python3
"""
Simple build script for creating an installer for the GitHub Repository Analyzer.
This script builds an installer that detects GPU availability at installation time.
Run directly with: python build_installer.py

WIP this does not work yet.
"""

import os
import sys
import subprocess
import logging
import shutil
import platform
import tempfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clean_build_files():
    """Clean previous build files before starting a new build"""
    logger.info("Cleaning previous build files...")
    
    # Clean PyInstaller cache and build directories
    for dir_name in ["build", "dist", "__pycache__"]:
        dir_path = os.path.join(os.getcwd(), dir_name)
        if os.path.exists(dir_path):
            logger.info(f"Removing directory: {dir_path}")
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                logger.warning(f"Error removing {dir_path}: {e}")
    
    # Remove previous build files
    for file_name in ["git_explain.spec", "installer.nsi", "gpu_detector.nsh", "Git_Explain_Setup.exe"]:
        file_path = os.path.join(os.getcwd(), file_name)
        if os.path.exists(file_path):
            logger.info(f"Removing file: {file_path}")
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Error removing {file_path}: {e}")

    # Clean NSIS temporary files (important to avoid the mmapping error)
    temp_dir = tempfile.gettempdir()
    if temp_dir and os.path.exists(temp_dir):
        try:
            for file_name in os.listdir(temp_dir):
                # NSIS temp files often start with "ns"
                if file_name.startswith("ns") and len(file_name) <= 8:
                    file_path = os.path.join(temp_dir, file_name)
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed NSIS temp file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not remove temp file {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Error cleaning temp directory: {e}")

def check_nsis():
    """Check if NSIS is installed and in PATH"""
    try:
        subprocess.run(['makensis', '/VERSION'], check=True, 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("✓ NSIS is installed and available")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("✗ NSIS (makensis) not found in PATH")
        logger.error("  Please install NSIS and make sure it's in your PATH")
        logger.error("  Download from: https://nsis.sourceforge.io/Download")
        return False

def install_dependencies(include_gpu=True):
    """Install all dependencies needed for both CPU and GPU operation"""
    logger.info("Installing dependencies...")
    
    # Install base dependencies first
    try:
        subprocess.run(["pip", "install", "-e", "."], check=True)
        logger.info("Base dependencies installed successfully")
    except Exception as e:
        logger.error(f"Error installing base dependencies: {e}")
        return False
    
    if include_gpu:
        try:
            # Install PyTorch with CUDA support
            logger.info("Installing PyTorch with CUDA support...")
            if platform.system() == "Windows":
                torch_cmd = "pip install torch --extra-index-url https://download.pytorch.org/whl/cu118/"
            else:
                torch_cmd = "pip install torch --extra-index-url https://download.pytorch.org/whl/cu118/"
                
            subprocess.run(torch_cmd.split(), check=True)
            
            # Install FAISS GPU
            logger.info("Installing FAISS GPU...")
            subprocess.run(["pip", "install", "faiss-gpu", "--force-reinstall"], check=True)
            
            # Install llama-cpp-python with CUDA
            logger.info("Installing llama-cpp-python with CUDA...")
            env = os.environ.copy()
            env["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
            
            if platform.system() == "Windows":
                # Windows needs a different approach
                os.environ["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
                subprocess.run(["pip", "install", "--force-reinstall", "llama-cpp-python"], check=True)
            else:
                subprocess.run(["pip", "install", "--force-reinstall", "llama-cpp-python"], env=env, check=True)
            
            logger.info("GPU dependencies installed successfully")
            return True
        except Exception as e:
            logger.error(f"Error installing GPU dependencies: {e}")
            logger.warning("Will continue with CPU-only build")
            return False
    
    return True

def create_spec_file():
    """Create the PyInstaller spec file for both CPU and GPU support"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
import sys

block_cipher = None

# Get the current directory
current_dir = os.getcwd()
src_dir = os.path.join(current_dir, 'src')

# UI asset paths
ui_templates = os.path.join(src_dir, 'ui', 'templates')
ui_static = os.path.join(src_dir, 'ui', 'static')

# Create required directories if they don't exist
for dir_path in [
    os.path.join(src_dir, 'ui'),
    ui_templates,
    ui_static,
    os.path.join(ui_static, 'css'),
    os.path.join(ui_static, 'js'),
    os.path.join(ui_static, 'img')
]:
    os.makedirs(dir_path, exist_ok=True)

# Collect imports for the app
hidden_imports = []

# Core Python modules
hidden_imports += [
    'threading', 'webbrowser', 'json', 'logging', 'pathlib',
    'tempfile', 'shutil', 'glob', 'ast', 're', 'pickle',
]

# Web and UI related
hidden_imports += [
    'flask', 'flask.templating', 'werkzeug', 'jinja2', 'webview',
    'engineio.async_drivers.threading',
]

# Network and API
hidden_imports += [
    'requests', 'httpx', 'urllib3'
]

# ML and data processing - include both CPU and GPU variants for compatibility
hidden_imports += [
    'numpy', 'torch', 'transformers', 
    'huggingface_hub', 'sentence_transformers', 'llama_cpp',
    'faiss'  # Include both CPU and GPU versions
]

# Git handling
hidden_imports += ['git', 'gitdb']

# Application modules
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
    'src.utils.progress',
    'src.utils.gpu_setup',
]

# Collect data files
datas = []

# UI assets
datas += [(ui_templates, 'ui/templates')]
datas += [(ui_static, 'ui/static')]

# Define the Analysis
a = Analysis(
    [os.path.join(src_dir, 'app_launcher.py')],
    pathex=[current_dir, src_dir],
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
    noarchive=False
)

# Create the executable
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='git-explain',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)

# Create the distributable folder
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='git-explain'
)
"""
    
    spec_file = os.path.join(os.getcwd(), "git_explain.spec")
    with open(spec_file, 'w') as f:
        f.write(spec_content)
    logger.info(f"Created PyInstaller spec file: {spec_file}")
    return spec_file

def create_nsis_script():
    """Create a very simple NSIS installer script with basic GPU detection"""
    nsis_content = """
; NSIS Installer Script for Git Explain
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"

; Define application name and installer filename
Name "Git Explain"
OutFile "Git_Explain_Setup.exe"

; Default installation directory
InstallDir "$PROGRAMFILES64\\Git Explain"

; Request application privileges
RequestExecutionLevel admin

; UI settings
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\\Contrib\\Graphics\\Icons\\modern-install.ico"

; Interface pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS  ; Add component selection page
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Set language
!insertmacro MUI_LANGUAGE "English"

; Variables
Var HasGPU

; Simple GPU detection approach using a system call
Function DetectNvidiaGPU
  ; Create a temporary file
  GetTempFileName $0
  
  ; Execute a simple system command to check for NVIDIA GPUs
  nsExec::ExecToStack 'cmd.exe /c "wmic path win32_VideoController get name | findstr /i NVIDIA > $0"'
  Pop $1 ; Return value
  Pop $2 ; Console output
  
  ; Check if the file has content (NVIDIA GPU was found)
  FileOpen $3 $0 r
  FileRead $3 $4
  FileClose $3
  
  ; Delete the temporary file
  Delete $0
  
  ; Check if we found NVIDIA in the output
  ${If} $4 == ""
    Push "false"
  ${Else}
    Push "true"
  ${EndIf}
FunctionEnd

; GPU detection on initialization
Function .onInit
  ; Detect GPU
  Call DetectNvidiaGPU
  Pop $HasGPU
  
  ${If} $HasGPU == "true"
    MessageBox MB_OK|MB_ICONINFORMATION "NVIDIA GPU detected! The application will be installed with GPU acceleration support."
  ${Else}
    MessageBox MB_OK|MB_ICONINFORMATION "No CUDA-compatible GPU detected. The application will be installed in CPU-only mode."
  ${EndIf}
FunctionEnd

; Main installation section (required)
Section "Git Explain (Required)" SecMain
    SectionIn RO  ; Read-only, cannot be deselected
    
    SetOutPath "$INSTDIR"
    
    ; Copy all files from the PyInstaller dist directory
    File /r "dist\\git-explain\\*.*"
    
    ; Create GPU info file that will be read at runtime
    FileOpen $0 "$INSTDIR\\gpu_info.txt" w
    FileWrite $0 "GPU_DETECTED=$HasGPU$\\r$\\n"
    FileClose $0
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\\uninstall.exe"
    
    ; Add uninstall information to Add/Remove Programs
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "DisplayName" "Git Explain"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "UninstallString" "$INSTDIR\\uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "DisplayIcon" "$INSTDIR\\git-explain.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "Publisher" "Git Explain"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "NoRepair" 1
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain" "GPUSupport" $HasGPU
SectionEnd

; Desktop shortcut section (optional)
Section "Desktop Shortcut" SecDesktop
    CreateShortcut "$DESKTOP\\Git Explain.lnk" "$INSTDIR\\git-explain.exe"
SectionEnd

; Start Menu shortcuts section (optional)
Section "Start Menu Shortcuts" SecStartMenu
    CreateDirectory "$SMPROGRAMS\\Git Explain"
    CreateShortcut "$SMPROGRAMS\\Git Explain\\Git Explain.lnk" "$INSTDIR\\git-explain.exe"
    CreateShortcut "$SMPROGRAMS\\Git Explain\\Uninstall.lnk" "$INSTDIR\\uninstall.exe"
SectionEnd

; Descriptions for sections (shown in component page)
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "The core application files (required)."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Create a shortcut on the desktop."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Create shortcuts in the Start Menu."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; Uninstallation section
Section "Uninstall"
    ; Remove installed files and directories
    RMDir /r "$INSTDIR"
    
    ; Remove Start Menu items
    RMDir /r "$SMPROGRAMS\\Git Explain"
    
    ; Remove desktop shortcut
    Delete "$DESKTOP\\Git Explain.lnk"
    
    ; Remove registry keys
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitExplain"
SectionEnd
"""
    
    nsis_file = os.path.join(os.getcwd(), "installer.nsi")
    with open(nsis_file, 'w') as f:
        f.write(nsis_content)
    logger.info(f"Created NSIS installer script: {nsis_file}")
    return nsis_file

def build_installer():
    """Build the installer using PyInstaller and NSIS with minimal complexity"""
    try:
        # Clean up before starting
        clean_build_files()
        
        # Check NSIS first
        if not check_nsis():
            return False
        
        # Install all dependencies (including both CPU and GPU versions)
        if not install_dependencies(include_gpu=True):
            logger.warning("Some GPU dependencies could not be installed, but will continue with build")
        
        # Create spec file for both CPU and GPU support
        spec_file = create_spec_file()
        
        # Run PyInstaller
        logger.info("Running PyInstaller to create distributable files...")
        pyinstaller_cmd = [
            sys.executable, '-m', 'PyInstaller',
            spec_file,
            '--clean', 
            '--noconfirm'
        ]
        subprocess.run(pyinstaller_cmd, check=True)
        
        # Create a very basic NSIS script - no GPU detection at all
        logger.info("Creating basic NSIS installer script...")
        nsis_content = """
; Basic NSIS Installer Script
!include "MUI2.nsh"

Name "Git Explain"
OutFile "Git_Explain_Setup.exe"
InstallDir "$PROGRAMFILES64\\Git Explain"
RequestExecutionLevel admin

!define MUI_ICON "${NSISDIR}\\Contrib\\Graphics\\Icons\\modern-install.ico"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section
    SetOutPath "$INSTDIR"
    File /r "dist\\git-explain\\*.*"
    
    ; Create a basic GPU info file - always set to true for now
    ; The app will detect GPU availability at runtime
    FileOpen $0 "$INSTDIR\\gpu_info.txt" w
    FileWrite $0 "GPU_DETECTED=runtime$\\r$\\n"
    FileClose $0
    
    WriteUninstaller "$INSTDIR\\uninstall.exe"
    CreateShortcut "$DESKTOP\\Git Explain.lnk" "$INSTDIR\\git-explain.exe"
SectionEnd

Section "Uninstall"
    RMDir /r "$INSTDIR"
    Delete "$DESKTOP\\Git Explain.lnk"
SectionEnd
"""
        
        nsis_file = os.path.join(os.getcwd(), "installer.nsi")
        with open(nsis_file, 'w') as f:
            f.write(nsis_content)
        
        # Run NSIS with diagnostics
        logger.info("Creating installer with NSIS (basic version)...")
        
        try:
            # First try with verbose logging to see the issue
            logger.info("Running NSIS with verbose logging...")
            verbose_output = subprocess.run(['makensis', '/V4', nsis_file], 
                                          capture_output=True, 
                                          text=True, 
                                          timeout=60)
            logger.info(f"NSIS verbose output: {verbose_output.stdout}")
            if verbose_output.stderr:
                logger.warning(f"NSIS errors: {verbose_output.stderr}")
                
            # Then try normal build with shorter timeout 
            logger.info("Running normal NSIS build...")
            subprocess.run(['makensis', nsis_file], check=True, timeout=120)
        except subprocess.TimeoutExpired:
            logger.error("NSIS process timed out, trying with maximum compression")
            # Try one more time with minimum compression to speed up
            try:
                subprocess.run(['makensis', '/X"SetCompressor /FINAL zlib"', nsis_file], check=True, timeout=120)
            except subprocess.TimeoutExpired:
                logger.error("NSIS process timed out again. Build failed.")
                return False
        
        # Check if installer was created
        installer_path = os.path.join(os.getcwd(), "Git_Explain_Setup.exe")
        if os.path.exists(installer_path):
            logger.info(f"✓ Installer created successfully: {installer_path}")
            logger.info(f"  Installer size: {os.path.getsize(installer_path) / (1024*1024):.2f} MB")
            logger.info(f"  Note: GPU support will be detected at runtime")
            return True
        else:
            logger.error("✗ Installer creation failed: output file not found")
            return False
            
    except Exception as e:
        logger.error(f"Error building installer: {e}")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("Git Explain Installer Builder")
    print("=" * 70)
    
    if build_installer():
        print("\n✓ Installer built successfully!")
        sys.exit(0)
    else:
        print("\n✗ Failed to build installer. See errors above.")
        sys.exit(1)