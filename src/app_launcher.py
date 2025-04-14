#!/usr/bin/env python3
"""
Desktop Application Launcher for GitHub Repository Analyzer
This script launches the web app in a desktop window using pywebview
and handles GPU/CPU configuration automatically.

WIP the installer portions do not work yet
"""

import os
import sys
import threading
import time
import traceback
import webview
import atexit
import logging
import subprocess
from pathlib import Path

# Setup logging to a file for debugging
def setup_logging():
    log_dir = os.path.expanduser("~")
    app_data_dir = get_app_data_dir()
    os.makedirs(app_data_dir, exist_ok=True)
    
    log_file = os.path.join(app_data_dir, "github-repo-analyzer.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('launcher')

def get_app_data_dir():
    """Return the appropriate directory for app data based on platform"""
    if sys.platform == 'win32':
        app_data = os.environ.get('APPDATA', os.path.expanduser("~"))
        return os.path.join(app_data, "GitHubRepoAnalyzer")
    elif sys.platform == 'darwin':  # macOS
        return os.path.expanduser("~/Library/Application Support/GitHubRepoAnalyzer")
    else:  # Linux and other Unix-like
        return os.path.expanduser("~/.config/github-repo-analyzer")

# Initialize logger
logger = setup_logging()

logger.info("="*50)
logger.info("Starting GitHub Repository Analyzer")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")

def check_gpu_availability():
    """Check if a CUDA-compatible GPU is available"""
    # First check if we're running from an installer that detected GPU
    # This ensures consistent behavior between build time and runtime
    try:
        # Check for GPU info file created during installation
        gpu_info_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gpu_info.txt')
        if os.path.exists(gpu_info_path):
            with open(gpu_info_path, 'r') as f:
                content = f.read()
                if 'GPU_DETECTED=true' in content.lower():
                    logger.info("GPU was detected during installation")
                    os.environ["GITHUB_ANALYZER_GPU_AVAILABLE"] = "1"
                    return True, {"name": "GPU detected at install time"}
                elif 'GPU_DETECTED=false' in content.lower():
                    logger.info("No GPU was detected during installation")
                    os.environ["GITHUB_ANALYZER_GPU_AVAILABLE"] = "0"
                    return False, None
    except Exception as e:
        logger.warning(f"Error checking installer GPU detection: {e}")
    
    # Fallback to runtime detection
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "Unknown GPU"
            cuda_version = torch.version.cuda
            logger.info(f"GPU available: {gpu_name} (CUDA {cuda_version})")
            
            # Set environment variable to indicate GPU is available
            os.environ["GITHUB_ANALYZER_GPU_AVAILABLE"] = "1"
            
            return True, {
                "name": gpu_name,
                "cuda_version": cuda_version
            }
        else:
            logger.info("GPU not available via PyTorch CUDA")
    except ImportError:
        logger.warning("PyTorch not available for GPU check")
    except Exception as e:
        logger.warning(f"Error checking GPU availability: {e}")
    
    # Check if llama-cpp-python has CUDA support as a fallback
    try:
        import llama_cpp
        has_cublas = getattr(llama_cpp, "has_cublas", False)
        if has_cublas:
            logger.info("llama-cpp-python has CUDA support")
            os.environ["GITHUB_ANALYZER_GPU_AVAILABLE"] = "1"
            return True, {"name": "Unknown GPU (llama-cpp CUDA support)"}
    except ImportError:
        logger.warning("llama-cpp-python not available for GPU check")
    except Exception as e:
        logger.warning(f"Error checking llama-cpp GPU support: {e}")
    
    # GPU not available
    os.environ["GITHUB_ANALYZER_GPU_AVAILABLE"] = "0"
    logger.info("No GPU detected, will use CPU only")
    return False, None

# Check GPU before starting the application
has_gpu, gpu_info = check_gpu_availability()

# Determine if we're running in a PyInstaller bundle, installed via pip, or development mode
def get_application_mode():
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        logger.info("Running as PyInstaller bundle")
        base_dir = Path(sys._MEIPASS)
        static_folder = base_dir / "ui" / "static"
        template_folder = base_dir / "ui" / "templates"
        mode = "bundle"
    else:
        # Development mode
        logger.info("Running in development mode")
        base_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        src_dir = base_dir / "src"
        static_folder = src_dir / "ui" / "static"
        template_folder = src_dir / "ui" / "templates"
        mode = "development"
    
    # Log the detected paths
    logger.info(f"Base dir: {base_dir}")
    logger.info(f"Static folder exists: {static_folder.exists()}")
    logger.info(f"Template folder exists: {template_folder.exists()}")
    if static_folder.exists():
        logger.info(f"Static folder contents: {list(static_folder.iterdir())}")
    if template_folder.exists():
        logger.info(f"Template folder contents: {list(template_folder.iterdir())}")
    
    return {
        "mode": mode,
        "base_dir": base_dir,
        "static_folder": static_folder,
        "template_folder": template_folder
    }

app_info = get_application_mode()
MODE = app_info["mode"]
BASE_DIR = app_info["base_dir"]

# Create a portable data directory structure
def ensure_data_dirs():
    # Use a platform-appropriate location for storing application data
    app_data_dir = get_app_data_dir()
    
    # Create data directories
    data_dirs = {
        "data": os.path.join(app_data_dir, "data"),
        "repos": os.path.join(app_data_dir, "data", "repos"),
        "indexes": os.path.join(app_data_dir, "data", "indexes"),
        "models": os.path.join(app_data_dir, "data", "models")
    }
    
    for name, path in data_dirs.items():
        os.makedirs(path, exist_ok=True)
        logger.info(f"Ensured {name} directory exists: {path}")
    
    return data_dirs

data_dirs = ensure_data_dirs()

# Set environment variables to help the application find its data
os.environ["GITHUB_ANALYZER_DATA_DIR"] = data_dirs["data"]
os.environ["GITHUB_ANALYZER_MODE"] = MODE

# Adjust Python path based on the detected mode
if MODE == "bundle":
    # For PyInstaller bundle
    sys.path.insert(0, str(BASE_DIR))
else:
    # For development mode
    src_dir = BASE_DIR / "src"
    sys.path.insert(0, str(BASE_DIR))
    if src_dir.exists():
        sys.path.insert(0, str(src_dir))

# Import the Flask app
logger.info("Importing Flask app")
try:
    if MODE == "bundle":
        try:
            from main import app
            logger.info("Imported main.app")
        except ImportError as e:
            logger.warning(f"Direct import failed: {e}")
            # Fall back to the src prefix import
            from src.main import app
            logger.info("Imported src.main.app")
    else:
        # Development mode
        from src.main import app
    
    # Import the config
    try:
        if MODE == "bundle":
            try:
                from config import Config
            except ImportError:
                from src.config import Config
        else:
            from src.config import Config
        
        config = Config()
        # Override config paths with our platform-specific paths
        config.data_dir = Path(data_dirs["data"])
        config.repos_dir = Path(data_dirs["repos"])
        config.index_dir = Path(data_dirs["indexes"])
        config.models_dir = Path(data_dirs["models"])
        
        # Update config with GPU information
        config.gpu_available = has_gpu
        if has_gpu and gpu_info:
            config.gpu_info = gpu_info
        
        # Access the PORT or set default
        PORT = getattr(config, 'PORT', 5000)
        
    except ImportError as e:
        logger.warning(f"Could not import Config: {e}")
        PORT = 5000
    
    logger.info(f"Using port {PORT}")
except ImportError as e:
    logger.error(f"Failed to import Flask app: {e}")
    logger.error(traceback.format_exc())
    input("Press Enter to exit...") # Allow user to see the error
    sys.exit(1)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    logger.error(traceback.format_exc())
    input("Press Enter to exit...") # Allow user to see the error
    sys.exit(1)

# Configure the Flask app
app.config['TEMPLATES_AUTO_RELOAD'] = False
app.config['SERVER_NAME'] = None

# Server thread
server_thread = None

def run_flask():
    """Run the Flask server in the current thread"""
    logger.info(f"Starting Flask server on port {PORT}")
    try:
        app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"Error running Flask server: {e}")
        logger.error(traceback.format_exc())

def start_server_thread():
    """Start Flask in a separate thread"""
    global server_thread
    server_thread = threading.Thread(target=run_flask)
    server_thread.daemon = True
    server_thread.start()
    logger.info("Flask server thread started")

def on_closed():
    """Handler for when the webview window is closed"""
    logger.info("Window closed, application will exit")
    # No need to explicitly terminate threads, Python will clean up

def launch_app():
    """Launch the application"""
    # Start the Flask server in a thread
    start_server_thread()
    
    # Wait for the server to start
    logger.info("Waiting for Flask server to start...")
    server_started = False
    for i in range(30):  # Wait up to 15 seconds
        try:
            import requests
            logger.info(f"Attempt {i+1}: Checking server status")
            response = requests.get(f'http://127.0.0.1:{PORT}/api/system-status')
            if response.status_code == 200:
                logger.info("Flask server is running")
                server_started = True
                break
            else:
                logger.warning(f"Server returned status code: {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.info("Connection refused, server not ready yet")
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            time.sleep(0.5)
    
    if not server_started:
        logger.error("Flask server didn't start in time")
        input("Press Enter to exit...") # Allow user to see the error
        sys.exit(1)
    
    # Create and start the webview
    logger.info("Creating webview window...")
    
    window_title = 'GitHub Repository Analyzer'
    if has_gpu:
        window_title += f" (GPU: {gpu_info.get('name', 'Enabled')})"
    
    webview.create_window(
        title=window_title,
        url=f'http://127.0.0.1:{PORT}',
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600)
    )
    
    # Start webview (blocks until window is closed)
    logger.info("Starting webview...")
    webview.start(debug=False)  # Changed debug from True to False
    logger.info("Webview closed")

def create_installer():
    """
    Create an installer for the application.
    This function uses NSIS (Nullsoft Scriptable Install System) to create 
    an installer for the application.
    """
    try:
        # First, check if NSIS is installed
        try:
            subprocess.run(['makensis', '/VERSION'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info("NSIS is installed, proceeding with installer creation")
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("NSIS not found. Please install NSIS to create installers.")
            return False
            
        # Create dist directory for PyInstaller output
        dist_dir = os.path.join(os.getcwd(), "installer_dist")
        os.makedirs(dist_dir, exist_ok=True)
        
        # Run PyInstaller to create distributable files
        logger.info("Running PyInstaller to create distributable files...")
        
        # Note: We'll use the spec file that already exists
        spec_file = os.path.join(os.getcwd(), "github_repo_analyzer.spec")
        if not os.path.exists(spec_file):
            logger.error(f"Spec file not found: {spec_file}")
            return False
            
        pyinstaller_cmd = [
            'pyinstaller',
            spec_file,
            '--distpath', dist_dir,
            '--workpath', os.path.join(os.getcwd(), "installer_build"),
            '--noconfirm'
        ]
        
        subprocess.run(pyinstaller_cmd, check=True)
        logger.info("PyInstaller completed successfully")
        
        # Create NSIS installer script
        nsis_script = """
        !include "MUI2.nsh"
        
        ; Define application name and installer filename
        Name "GitHub Repository Analyzer"
        OutFile "GitHubRepoAnalyzer_Setup.exe"
        
        ; Default installation directory
        InstallDir "$PROGRAMFILES64\\GitHub Repository Analyzer"
        
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
        
        ; Main installation section (required)
        Section "Git Explain (Required)" SecMain
            SectionIn RO  ; Read-only, cannot be deselected
            
            SetOutPath "$INSTDIR"
            
            ; Copy all files from the PyInstaller dist directory
            File /r "installer_dist\\github-repo-analyzer\\*.*"
            
            ; Create uninstaller
            WriteUninstaller "$INSTDIR\\uninstall.exe"
            
            ; Add uninstall information to Add/Remove Programs
            WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer" "DisplayName" "GitHub Repository Analyzer"
            WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer" "UninstallString" "$INSTDIR\\uninstall.exe"
            WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer" "InstallLocation" "$INSTDIR"
            WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer" "DisplayIcon" "$INSTDIR\\github-repo-analyzer.exe"
            WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer" "Publisher" "GitHub Repository Analyzer"
            WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer" "NoModify" 1
            WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer" "NoRepair" 1
        SectionEnd
        
        ; Desktop shortcut section (optional)
        Section "Desktop Shortcut" SecDesktop
            CreateShortcut "$DESKTOP\\GitHub Repository Analyzer.lnk" "$INSTDIR\\github-repo-analyzer.exe"
        SectionEnd
        
        ; Start Menu shortcuts section (optional)
        Section "Start Menu Shortcuts" SecStartMenu
            CreateDirectory "$SMPROGRAMS\\GitHub Repository Analyzer"
            CreateShortcut "$SMPROGRAMS\\GitHub Repository Analyzer\\GitHub Repository Analyzer.lnk" "$INSTDIR\\github-repo-analyzer.exe"
            CreateShortcut "$SMPROGRAMS\\GitHub Repository Analyzer\\Uninstall.lnk" "$INSTDIR\\uninstall.exe"
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
            RMDir /r "$SMPROGRAMS\\GitHub Repository Analyzer"
            
            ; Remove desktop shortcut
            Delete "$DESKTOP\\GitHub Repository Analyzer.lnk"
            
            ; Remove registry keys
            DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\GitHubRepoAnalyzer"
        SectionEnd
        """
        
        # Write NSIS script to a file
        nsis_file = os.path.join(os.getcwd(), "installer.nsi")
        with open(nsis_file, 'w') as f:
            f.write(nsis_script)
        
        # Run NSIS to create the installer
        logger.info("Creating installer with NSIS...")
        subprocess.run(['makensis', nsis_file], check=True)
        
        # Check if installer was created successfully
        installer_path = os.path.join(os.getcwd(), "GitHubRepoAnalyzer_Setup.exe")
        if os.path.exists(installer_path):
            logger.info(f"Installer created successfully: {installer_path}")
            return True
        else:
            logger.error("Installer creation failed: output file not found")
            return False
            
    except Exception as e:
        logger.error(f"Error creating installer: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == '__main__':
    # Check for installer creation argument
    if len(sys.argv) > 1 and sys.argv[1] == '--create-installer':
        print("Creating installer...")
        if create_installer():
            print("Installer created successfully!")
        else:
            print("Installer creation failed. Check the logs for details.")
            sys.exit(1)
    else:
        try:
            launch_app()
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
        except Exception as e:
            logger.error(f"Unhandled exception: {e}")
            logger.error(traceback.format_exc())
            input("Press Enter to exit...") # Allow user to see the error
        finally:
            logger.info("Application exiting")