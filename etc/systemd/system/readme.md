# Warning
starting your python scripts as system services will log prints and outputs of scripts in system log files, which can quickly fill your harddrive/sd-card, use with caution.

# Setup
create a "your-python-script.service" in /etc/sytemd/system/

"

[Unit]

Description=My Python Script
After=network.target

[Service]

ExecStart=/usr/bin/python3 /path/to/my-script.py
Restart=always
User=pi

[Install]

WantedBy=multi-user.target

"

# reload services 
sudo systemctl daemon-reload

# starting / stoping

sudo systemctl start my-python-script
sudo systemctl stop my-python-script

# Timers

create timer file:
sudo nano /etc/systemd/system/my-python-script.timer

"

[Unit]

Description=Timer to stop and restart my Python script

[Timer]

OnBootSec=10min
OnUnitActiveSec=10min

[Install]

WantedBy=timers.target

"


This timer will trigger the my-python-script.service unit every 10 minutes.
