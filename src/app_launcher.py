#!/usr/bin/env python3
"""
Desktop Application Launcher for GitHub Repository Analyzer
This script launches the web app in a desktop window using pywebview

WIP: does not work yet
"""

import os
import sys
import threading
import time
import traceback
import webview
import atexit
import logging
from pathlib import Path

# Setup logging to a file for debugging
log_dir = os.path.expanduser("~")
log_file = os.path.join(log_dir, "github-repo-analyzer.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('launcher')

logger.info("="*50)
logger.info("Starting GitHub Repository Analyzer")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")

# Determine if we're running in a PyInstaller bundle
if getattr(sys, 'frozen', False):
    # Running in a bundle
    logger.info("Running as PyInstaller bundle")
    BASE_DIR = Path(sys._MEIPASS)
    # When running as a bundle, paths are relative to the bundle root
    STATIC_FOLDER = BASE_DIR / "ui" / "static"
    TEMPLATE_FOLDER = BASE_DIR / "ui" / "templates"
    
    # For PyInstaller, these must be explicitly in sys.path
    sys.path.insert(0, str(BASE_DIR))
    
    logger.info(f"Base dir: {BASE_DIR}")
    logger.info(f"Static folder exists: {STATIC_FOLDER.exists()}")
    logger.info(f"Template folder exists: {TEMPLATE_FOLDER.exists()}")
    if STATIC_FOLDER.exists():
        logger.info(f"Static folder contents: {list(STATIC_FOLDER.iterdir())}")
    if TEMPLATE_FOLDER.exists():
        logger.info(f"Template folder contents: {list(TEMPLATE_FOLDER.iterdir())}")
else:
    # Running in a normal Python environment
    logger.info("Running in development mode")
    # Get the base directory (project root)
    BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # The src directory is a direct child of BASE_DIR
    SRC_DIR = BASE_DIR / "src"
    STATIC_FOLDER = SRC_DIR / "ui" / "static"
    TEMPLATE_FOLDER = SRC_DIR / "ui" / "templates"
    
    # Add to Python path
    sys.path.insert(0, str(BASE_DIR))
    if SRC_DIR.exists():
        sys.path.insert(0, str(SRC_DIR))
    
    logger.info(f"Base dir: {BASE_DIR}")
    logger.info(f"Src dir exists: {SRC_DIR.exists()}")

# Import the Flask app
logger.info("Importing Flask app")
try:
    if getattr(sys, 'frozen', False):
        # When frozen, try direct imports first
        logger.info(f"sys.path: {sys.path}")
        try:
            from main import app
            logger.info("Imported main.app")
        except ImportError as e:
            logger.warning(f"Direct import failed: {e}")
            # Fall back to the src prefix import
            from src.main import app
            logger.info("Imported src.main.app")
    else:
        # Development mode import
        from src.main import app
    
    # Import the config
    try:
        if getattr(sys, 'frozen', False):
            try:
                from config import Config
            except ImportError:
                from src.config import Config
        else:
            from src.config import Config
        
        config = Config()
        # Access the PORT or set default
        PORT = getattr(config, 'PORT', 5000)
        
        # Ensure directories exist
        os.makedirs(config.data_dir, exist_ok=True)
        os.makedirs(config.repos_dir, exist_ok=True)
        os.makedirs(config.index_dir, exist_ok=True)
        
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
    webview.create_window(
        title='GitHub Repository Analyzer',
        url=f'http://127.0.0.1:{PORT}',
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600)
    )
    
    # Start webview (blocks until window is closed)
    logger.info("Starting webview...")
    webview.start(debug=True)
    logger.info("Webview closed")

if __name__ == '__main__':
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