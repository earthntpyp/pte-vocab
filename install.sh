#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.user.ptevocab"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
PYTHON=$(which python3)

echo "Installing PTE Vocab as a login item..."
echo "  Script  : $SCRIPT_DIR/pte_vocab.py"
echo "  Python  : $PYTHON"
echo "  Plist   : $PLIST_PATH"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/pte_vocab.py</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/pte_vocab.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/pte_vocab_error.log</string>
</dict>
</plist>
EOF

# Unload if already loaded
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load
launchctl load "$PLIST_PATH"

echo ""
echo "Done! PTE Vocab will now run automatically every time you log in."
echo "Send a test alert now with:"
echo "  python3 $SCRIPT_DIR/pte_vocab.py now"
