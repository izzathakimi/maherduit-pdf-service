#!/bin/bash
# Simple beep/notification script for task completion

echo "🔊 Task Completed! 🎉"
echo "=============================="
echo "$(date): Claude has finished the current task"
echo "=============================="

# Try different notification methods
if command -v notify-send >/dev/null 2>&1; then
    notify-send "Claude Code" "Task completed successfully! 🎉"
    echo "📱 Desktop notification sent"
elif command -v osascript >/dev/null 2>&1; then
    osascript -e 'display notification "Task completed successfully! 🎉" with title "Claude Code"'
    echo "📱 macOS notification sent"
elif command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Task completed successfully!', 'Claude Code')"
    echo "📱 Windows notification sent"
fi

# Try to play the sound file if it exists
if [ -f "task_complete.wav" ]; then
    if command -v aplay >/dev/null 2>&1; then
        aplay task_complete.wav 2>/dev/null
        echo "🔊 Played sound with aplay"
    elif command -v paplay >/dev/null 2>&1; then
        paplay task_complete.wav 2>/dev/null
        echo "🔊 Played sound with paplay"
    elif command -v afplay >/dev/null 2>&1; then
        afplay task_complete.wav 2>/dev/null
        echo "🔊 Played sound with afplay"
    else
        echo "🔇 Sound file created but no audio player found"
    fi
fi

# Terminal bell as fallback
printf '\a'
echo "🔔 Terminal bell sent"