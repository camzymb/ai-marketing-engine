# Install guide

This guide sets up the AI Marketing Engine on your own computer. Nothing runs on anyone's website, and you use your own Claude API key. Plan for about 20 minutes.

## What you need on every computer

- **A Claude API key.** Make one in the Claude Console at platform.claude.com, under **API keys**. Give it a low spend limit first, for example $5. A full test run of 20 leads costs about $0.02.
- **Node.js 18 or newer.** It runs the demo and the agents.
- **Python 3.10 or newer.** It builds the prompts and the n8n workflow.
- **Git.** You use it to download the project.
- **n8n (optional).** You only need it to connect real forms, HubSpot and email. It can be n8n Cloud or self-hosted.

## Windows

1. **Install the tools.** Open **PowerShell** and run:
   ```powershell
   winget install OpenJS.NodeJS.LTS
   winget install Python.Python.3.12
   winget install Git.Git
   ```
   Close PowerShell and open it again so it finds the new tools.
2. **Download the project.**
   ```powershell
   cd $HOME\Documents
   git clone https://github.com/camzymb/ai-marketing-engine.git
   cd ai-marketing-engine
   ```
3. **Add your settings.**
   ```powershell
   copy .env.example .env
   notepad .env
   ```
   Paste your API key after `ANTHROPIC_API_KEY=` and fill in your name and alert email. Save and close.
4. **Build and try it.**
   ```powershell
   py scripts\build.py
   node demo\server.js --mock
   ```
   Open http://127.0.0.1:8787/dashboard.html in your browser. The mock run uses no credits. Press **Ctrl+C** to stop it.
5. **Run it for real.**
   ```powershell
   node demo\server.js
   ```

## macOS

1. **Install the tools.** Install [Homebrew](https://brew.sh) if you don't have it, then open **Terminal** and run:
   ```bash
   brew install node python git
   ```
2. **Download the project.**
   ```bash
   cd ~/Documents
   git clone https://github.com/camzymb/ai-marketing-engine.git
   cd ai-marketing-engine
   ```
3. **Add your settings.**
   ```bash
   cp .env.example .env
   chmod 600 .env
   open -e .env
   ```
   Paste your API key and fill in the rest, then save. `chmod 600` means only your user account can read the file.
4. **Build and try it.**
   ```bash
   python3 scripts/build.py
   node demo/server.js --mock
   ```
   Open http://127.0.0.1:8787/dashboard.html. Press **Ctrl+C** to stop.
5. **Run it for real.**
   ```bash
   node demo/server.js
   ```

## Linux (Ubuntu or Debian)

1. **Install the tools.**
   ```bash
   sudo apt update
   sudo apt install -y nodejs npm python3 git
   node --version
   ```
   If the version is below 18, install a newer Node.js from nodejs.org or with nvm.
2. **Download the project.**
   ```bash
   git clone https://github.com/camzymb/ai-marketing-engine.git
   cd ai-marketing-engine
   ```
3. **Add your settings.**
   ```bash
   cp .env.example .env
   chmod 600 .env
   nano .env
   ```
4. **Build and try it.**
   ```bash
   python3 scripts/build.py
   node demo/server.js --mock
   ```
   Open http://127.0.0.1:8787/dashboard.html.
5. **Run it for real.**
   ```bash
   node demo/server.js
   ```

## Record the demo (optional)

`demo/record.js` films the dashboard as a vertical video for social media. It needs Playwright:

```bash
npm install playwright
npx playwright install chromium
node demo/server.js --port=8787 &
node demo/record.js my-run 8787
```

## Connect real leads with n8n

1. Run `python scripts/build.py`. It writes `n8n/lead-loop.json` with your settings and context file inside.
2. Follow [docs/lead-loop-setup.md](docs/lead-loop-setup.md) to import it, connect your Anthropic, HubSpot and Gmail accounts in n8n, and test it.
3. In n8n, the API key is stored as an n8n credential. Never paste it into a node.

## If something goes wrong

| Problem | What to do |
| --- | --- |
| `ANTHROPIC_API_KEY` is missing | Check that `.env` is in the project folder and the line has no spaces around `=`. |
| Error 401 | The key is wrong or was deleted. Make a new one. |
| Error 429 or a spend-limit error | You hit a rate or spend limit. Wait, or raise the limit in the Claude Console. |
| `python` isn't found on Windows | Use `py` instead of `python`. |
| The page doesn't open | Use `127.0.0.1`, not your computer's network address. The demo only listens on your own computer. |
