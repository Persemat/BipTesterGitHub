"""
E2E Test Orchestrator.
Manages the lifecycle of Ngrok, the Node.js Proxy, and Botium CLI to execute
generated tests sequentially and avoid cross-talk on Infobip Open Channel.
"""

import os
import shutil
import sys
import time
import glob
import subprocess
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

PROXY_PORT = os.getenv("PROXY_PORT", "3000")
PROXY_SCRIPT = os.getenv("PROXY_SCRIPT_PATH", "proxy.js")
BOTIUM_TEST_DIR = os.getenv("BOTIUM_TEST_DIR", "botium/spec/generated_tests")
BOTIUM_UTT_DIR = os.getenv("BOTIUM_UTT_DIR", "botium/spec/generated_tests/utterances")
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "3"))

def start_ngrok():
    """Starts Ngrok in the background and retrieves the public HTTPS URL."""
    print(f"[1] Starting Ngrok on port {PROXY_PORT}...")
    
    # Start ngrok silently
    ngrok_process = subprocess.Popen(
        ["ngrok", "http", PROXY_PORT], 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )
    
    public_url = None
    # Poll the local Ngrok API until the tunnel is ready
    for _ in range(15):
        try:
            time.sleep(1)
            response = requests.get("http://127.0.0.1:4040/api/tunnels")
            if response.status_code == 200:
                tunnels = response.json().get("tunnels", [])
                for tunnel in tunnels:
                    if tunnel.get("public_url", "").startswith("https"):
                        public_url = tunnel["public_url"]
                        break
            if public_url:
                break
        except requests.ConnectionError:
            continue

    if not public_url:
        print("❌ Error: Could not retrieve Ngrok public URL.")
        ngrok_process.terminate()
        sys.exit(1)

    print(f"✅ Ngrok is live! Public URL: {public_url}")
    return ngrok_process, public_url

def start_proxy(public_url):
    """Starts the Node.js proxy, injecting the Ngrok URL as an environment variable."""
    print("[2] Starting Node.js Proxy...")
    
    # Copy current environment and add the WEBHOOK_URL
    env = os.environ.copy()
    env["WEBHOOK_URL"] = public_url 
    
    # shell=True is often required on Windows for 'node' commands
    proxy_process = subprocess.Popen(
        ["node", PROXY_SCRIPT], 
        env=env,
        shell=(os.name == 'nt')
    )
    time.sleep(3) # Give Express server time to bind to the port
    print("✅ Proxy successfully started!")
    return proxy_process

def run_botium_isolated(public_url):
    print("\n[3] Preparing Botium Configuration...")
    
    # 1. Read the botium.template.json
    if not os.path.exists("botium.template.json"):
        print("❌ ERRORE: File botium.template.json non trovato!")
        return

    with open("botium.template.json", "r", encoding="utf-8") as f:
        config_text = f.read()
        
    # 2. Inject the Ngrok URL and Infobip credentials into the botium.json template
    webhook_url = f"{public_url}{os.getenv('WEBHOOK_ENDPOINT', '/api/botium-webhook')}"
    config_text = config_text.replace("<NGROK_URL>", webhook_url)
    config_text = config_text.replace("<INFOBIP_API_KEY>", os.getenv("INFOBIP_API_KEY", ""))
    config_text = config_text.replace("<DESTINATION>", os.getenv("INFOBIP_CHANNEL_ID", ""))
    config_text = config_text.replace("<INFOBIP_BASE_URL>", os.getenv("INFOBIP_BASE_URL", "https://api.infobip.com"))
    
    # 3. Create the botium.json file dynamically
    with open("botium.json", "w", encoding="utf-8") as f:
        f.write(config_text)
        
    print("✅ botium.json dynamically generated.")

    json_report_dir = os.path.join("reports", "json")
    html_report_dir = os.path.join("reports", "html")
    if os.path.exists("reports"):
        shutil.rmtree("reports")
    os.makedirs(json_report_dir, exist_ok=True)

    print("\n[4] Starting Isolated E2E Tests...")
    convo_files = glob.glob(os.path.join(BOTIUM_TEST_DIR, "*.convo.txt"))
    utterances_dir = BOTIUM_UTT_DIR
    
    if not convo_files:
        print(f"⚠️ No test files found in {BOTIUM_TEST_DIR}")
        return

    passed, failed = 0, 0
    npx_cmd = "npx.cmd" if os.name == "nt" else "npx"

    for idx, convo in enumerate(convo_files, start=1):
        filename = os.path.basename(convo)
        print(f"\n--- Running Test {idx}/{len(convo_files)}: {filename} ---")
        
        # Construct the Botium CLI command; a json report will be generated for each test
        botium_cmd = [
            npx_cmd, "botium-cli", "run", "mochawesome",
            "--convos", convo,
            "--convos", utterances_dir,
            "--reporter-options", f"reportDir={json_report_dir},reportFilename=test_{idx},html=false,json=true"
        ]

        # DEBUG ATTIVATO
        debug_env = os.environ.copy()
        debug_env["DEBUG"] = "botium-connector-simplerest*"
        
        result = subprocess.run(botium_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ PASSED: {filename}")
            passed += 1
        else:
            print(f"❌ FAILED: {filename}")
            failed += 1
            print("--- STDOUT   ---")
            print(result.stdout)
            print("--- Error Details ---")
            print(result.stderr)
            print("------------------------")
        
        # IL TUO FONDAMENTALE COOLDOWN
        if idx < len(convo_files):
            print(f"⏳ Cooldown ({COOLDOWN_SECONDS}s) to prevent cross-talk...")
            time.sleep(COOLDOWN_SECONDS)


    print("\n[5] Generating Consolidated Mochawesome Report...")
    merged_json = os.path.join("reports", "merged.json")
    
    merge_res = subprocess.run(
        [npx_cmd, "mochawesome-merge", f"{json_report_dir}/*.json"],
        capture_output=True, text=True
    )
    with open(merged_json, "w", encoding="utf-8") as f:
        f.write(merge_res.stdout)

    subprocess.run([npx_cmd, "marge", merged_json, "-o", html_report_dir, "--inline"])


    print("\n" + "="*40)
    print(f"🎯 FINAL RESULTS: {passed} Passed, {failed} Failed.")
    print(f"📊 Report HTML ready in: {os.path.join(html_report_dir, 'merged.html')}")
    print("="*40)

def main():
    ngrok_proc, proxy_proc = None, None
    try:
        ngrok_proc, public_url = start_ngrok()
        proxy_proc = start_proxy(public_url)
        run_botium_isolated(public_url)
    except KeyboardInterrupt:
        print("\n⚠️ Manual interruption detected (Ctrl+C).")
    finally:
        print("\n[4] Cleaning up environment (Terminating Ngrok and Proxy)...")
        if proxy_proc:
            proxy_proc.terminate()
        if ngrok_proc:
            ngrok_proc.terminate()
        if os.path.exists("botium.json"):
            os.remove("botium.json")
        print("✅ Environment clean. Exiting.")

if __name__ == "__main__":
    main()