#!/usr/bin/env python3
"""
Pomodoro CLI - A simple command-line Pomodoro timer
Track your focus sessions and breaks with ease.
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

# Configuration
WORK_DURATION = 25 * 60  # 25 minutes
SHORT_BREAK = 5 * 60     # 5 minutes
LONG_BREAK = 15 * 60     # 15 minutes
HISTORY_FILE = Path.home() / ".pomodoro_history.json"


def load_history():
    """Load pomodoro history from JSON file."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {"sessions": [], "total_completed": 0}


def save_session(session_type, duration):
    """Save a completed session to history."""
    history = load_history()
    history["sessions"].append({
        "type": session_type,
        "duration": duration,
        "completed_at": datetime.now().isoformat()
    })
    if session_type == "work":
        history["total_completed"] += 1
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def format_time(seconds):
    """Format seconds into MM:SS."""
    mins, secs = divmod(int(seconds), 60)
    return f"{mins:02d}:{secs:02d}"


def countdown(duration, session_type):
    """Run a countdown timer with live updates."""
    start_time = time.time()
    end_time = start_time + duration
    
    print(f"\n🍅 {session_type.upper()} SESSION - {format_time(duration)}")
    print("Press Ctrl+C to stop\n")
    
    try:
        while time.time() < end_time:
            remaining = end_time - time.time()
            print(f"\r⏱️  {format_time(remaining)} ", end='', flush=True)
            time.sleep(1)
        
        print(f"\n\n✅ {session_type.capitalize()} complete!\n")
        save_session(session_type, duration)
        return True
        
    except KeyboardInterrupt:
        print(f"\n\n⏸️  Session interrupted.\n")
        return False


def show_stats():
    """Display pomodoro statistics."""
    history = load_history()
    total = history["total_completed"]
    
    print("\n📊 POMODORO STATS")
    print("=" * 40)
    print(f"Total completed: {total} 🍅")
    
    if history["sessions"]:
        recent = history["sessions"][-5:]
        print(f"\nRecent sessions:")
        for s in recent:
            timestamp = datetime.fromisoformat(s["completed_at"]).strftime("%Y-%m-%d %H:%M")
            print(f"  • {s['type']:5s} - {timestamp}")
    else:
        print("\nNo sessions yet. Start your first pomodoro!")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="🍅 Pomodoro CLI - Stay focused, take breaks",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('action', 
                       choices=['work', 'break', 'long', 'stats'],
                       help='Action: work (25m), break (5m), long (15m), stats')
    
    parser.add_argument('-t', '--time',
                       type=int,
                       help='Custom duration in minutes')
    
    args = parser.parse_args()
    
    if args.action == 'stats':
        show_stats()
        return
    
    # Determine duration
    durations = {
        'work': WORK_DURATION,
        'break': SHORT_BREAK,
        'long': LONG_BREAK
    }
    
    duration = args.time * 60 if args.time else durations[args.action]
    
    # Run the timer
    countdown(duration, args.action)


if __name__ == "__main__":
    main()
