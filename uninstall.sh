#!/usr/bin/env bash
PLIST_PATH="$HOME/Library/LaunchAgents/com.user.ptevocab.plist"
launchctl unload "$PLIST_PATH" 2>/dev/null || true
rm -f "$PLIST_PATH"
echo "PTE Vocab background service removed."
