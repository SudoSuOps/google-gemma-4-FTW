#!/bin/bash
# Deploy the deed recorder to zima-2 edge box
# Run from swarmrails: bash edge/deploy_recorder.sh

set -e
EDGE="edge@192.168.0.230"
REMOTE_DIR="/home/edge/deed-recorder"

echo "═══ Deploying Deed Recorder to zima-2 edge ═══"

# 1. Create remote directory
ssh $EDGE "mkdir -p $REMOTE_DIR"

# 2. Copy recorder
scp edge/deed_recorder.py $EDGE:$REMOTE_DIR/deed_recorder.py
echo "  [1/4] Copied deed_recorder.py"

# 3. Install psycopg2 on edge
ssh $EDGE "pip3 install --user psycopg2-binary 2>&1 | tail -2"
echo "  [2/4] Installed psycopg2"

# 4. Create systemd service
ssh $EDGE "echo 'mack' | sudo -S bash -c 'cat > /etc/systemd/system/deed-recorder.service << EOF
[Unit]
Description=SwarmChain Deed Recorder
After=network-online.target remote-fs.target
Wants=network-online.target

[Service]
Type=simple
User=edge
WorkingDirectory=/home/edge/deed-recorder
Environment=DATABASE_URL=postgresql://swarm:swarmandbee2026@192.168.0.102:5433/swarmgraph
Environment=NAS_DEEDS_PATH=/mnt/swarm/datasets
ExecStart=/usr/bin/python3 /home/edge/deed-recorder/deed_recorder.py --poll 30 --batch-size 50
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=deed-recorder

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable deed-recorder
systemctl start deed-recorder
'"
echo "  [3/4] Service installed and started"

# 5. Verify
sleep 3
ssh $EDGE "systemctl is-active deed-recorder && journalctl -u deed-recorder --no-pager -n 10"
echo "  [4/4] Verified"

echo ""
echo "═══ Deed Recorder deployed to $EDGE ═══"
echo "  Service: deed-recorder.service (auto-starts on boot)"
echo "  Logs:    ssh $EDGE journalctl -u deed-recorder -f"
echo "  Stop:    ssh $EDGE sudo systemctl stop deed-recorder"
echo "  Restart: ssh $EDGE sudo systemctl restart deed-recorder"
