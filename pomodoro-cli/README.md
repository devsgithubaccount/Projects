# 🍅 Pomodoro CLI

A lightweight command-line Pomodoro timer to boost your productivity. Track focus sessions, take breaks, and view your stats.

## Features

- ⏱️  **25-minute work sessions** (classic Pomodoro)
- ☕ **5-minute short breaks**
- 🌴 **15-minute long breaks**
- 📊 **Session tracking & statistics**
- ⚙️  **Custom durations**
- 💾 **Automatic history saving**

## Installation

```bash
# Clone the repo
git clone https://github.com/Devsgithubaccount/pomodoro-cli.git
cd pomodoro-cli

# Make it executable
chmod +x pomodoro.py

# Optional: Add to PATH
ln -s $(pwd)/pomodoro.py ~/.local/bin/pomodoro
```

## Usage

### Basic Commands

```bash
# Start a 25-minute work session
./pomodoro.py work

# Take a 5-minute break
./pomodoro.py break

# Take a 15-minute long break
./pomodoro.py long

# View your stats
./pomodoro.py stats
```

### Custom Duration

```bash
# Custom 45-minute work session
./pomodoro.py work -t 45

# Custom 10-minute break
./pomodoro.py break -t 10
```

## How It Works

1. **Start a session** - Choose work, break, or long break
2. **Timer counts down** - Live display shows remaining time
3. **Session completes** - Auto-saved to `~/.pomodoro_history.json`
4. **Track progress** - View stats anytime with `stats` command

## Examples

```bash
# Typical workflow
./pomodoro.py work    # 25 min focus
./pomodoro.py break   # 5 min rest
./pomodoro.py work    # 25 min focus
./pomodoro.py break   # 5 min rest
./pomodoro.py work    # 25 min focus
./pomodoro.py long    # 15 min rest

# Check your progress
./pomodoro.py stats
```

## Requirements

- Python 3.6+
- No external dependencies (uses standard library only!)

## License

MIT License - Build something awesome! 🚀

## Author

Built by Grog 🤖 for Dev
