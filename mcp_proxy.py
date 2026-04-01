import sys
import subprocess
import threading
import json
import os
import logging
import shutil


LOG_DIR = r"C:\MCP_Audit"
LOG_FILE = os.path.join(LOG_DIR, "mcp.log")


if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except Exception:
        LOG_FILE = os.path.join(os.getenv('TEMP'), "mcp_fallback.log")


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - [PID:%(process)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log_traffic(direction, data):
    """Writes traffic to the log file."""
    try:
        payload = json.loads(data)
        method = payload.get("method", "unknown")
        msg_id = payload.get("id", "?")
        # Log specific tool usage or errors clearly
        if "error" in payload:
             logging.error(f"[{direction.upper()}] ID:{msg_id} | ERROR: {payload['error']}")
        else:
             logging.info(f"[{direction.upper()}] Method: {method} | ID: {msg_id} | Payload: {data.strip()[:1000]}")
    except:
        logging.info(f"[{direction.upper()}] RAW: {data.strip()[:1000]}")

def stream_relay(source, dest, direction, log_func):
    """Reads from source, logs, and writes to dest."""
    for line in iter(source.readline, b''):
        if line:
            try:
                text = line.decode('utf-8', errors='ignore')
                log_func(direction, text)
            except Exception:
                pass
            
            try:
                dest.write(line)
                dest.flush()
            except (BrokenPipeError, IOError):
                break
        else:
            break

def resolve_command(cmd_list):
    """Fixes command lookup for Windows"""
    cmd = cmd_list[0]
    
    # 1. Windows Fix: Append .cmd to npx/npm if missing
    if sys.platform == "win32":
        if cmd.lower() in ["npx", "npm"] and not cmd.lower().endswith(".cmd"):
            cmd_list[0] = f"{cmd}.cmd"

    # 2. Absolute Path check (Optional but safer)
    # If the command isn't a path, let subprocess find it in PATH
    return cmd_list

def main():
    raw_command = sys.argv[1:]
    
    if not raw_command:
        logging.error("No command provided to proxy.")
        sys.exit(1)

    # APPLY THE FIX HERE
    command = resolve_command(raw_command)

    logging.info(f"--- STARTING PROXY FOR: {' '.join(command)} ---")

    try:
        # Start the Real Node.js Server
        # shell=False is preferred for signal handling, but requires the .cmd fix above
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr, 
            env=os.environ.copy()
        )

        t_in = threading.Thread(target=stream_relay, args=(sys.stdin.buffer, process.stdin, "request", log_traffic))
        t_out = threading.Thread(target=stream_relay, args=(process.stdout, sys.stdout.buffer, "response", log_traffic))

        t_in.daemon = True
        t_out.daemon = True
        t_in.start()
        t_out.start()

        process.wait()
        
    except FileNotFoundError:
        # This catches the specific WinError 2 and logs it clearly
        logging.critical(f"EXECUTABLE NOT FOUND: Could not find '{command[0]}'. Ensure Node.js is installed and in your PATH.")
    except Exception as e:
        logging.critical(f"Proxy Fatal Error: {e}")
    finally:
        logging.info("--- PROXY STOPPED ---")

if __name__ == "__main__":
    main()
