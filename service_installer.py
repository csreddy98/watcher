
import os
import sys
import platform

def create_systemd_service():
    service_content = """[Unit]
Description=File Watcher Service
After=network.target

[Service]
Type=simple
User={user}
ExecStart={python} {script_path} --daemon
Restart=always

[Install]
WantedBy=multi-user.target
""".format(
        user=os.getenv('USER'),
        python=sys.executable,
        script_path=os.path.abspath('app.py')
    )
    
    service_path = '/etc/systemd/system/file_watcher.service'
    try:
        with open(service_path, 'w') as f:
            f.write(service_content)
        os.system('sudo systemctl daemon-reload')
        os.system('sudo systemctl enable file_watcher')
        os.system('sudo systemctl start file_watcher')
        print("Service installed successfully!")
    except Exception as e:
        print(f"Error installing service: {str(e)}")

def create_launchd_service():
    plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.file_watcher</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{script_path}</string>
        <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
""".format(
        python=sys.executable,
        script_path=os.path.abspath('app.py')
    )
    
    plist_path = os.path.expanduser('~/Library/LaunchAgents/com.user.file_watcher.plist')
    try:
        with open(plist_path, 'w') as f:
            f.write(plist_content)
        os.system(f'launchctl load {plist_path}')
        print("Service installed successfully!")
    except Exception as e:
        print(f"Error installing service: {str(e)}")

def main():
    system = platform.system()
    if system == 'Linux':
        create_systemd_service()
    elif system == 'Darwin':  # macOS
        create_launchd_service()
    elif system == 'Windows':
        print("For Windows, please install NSSM (Non-Sucking Service Manager) and run:")
        print(f"nssm install FileWatcher {sys.executable} {os.path.abspath('app.py')} --daemon")
    else:
        print(f"Unsupported operating system: {system}")

if __name__ == "__main__":
    main()