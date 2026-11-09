// Loads settings from the .env file in the project folder into process.env.
// No extra packages needed. Values already set in your shell win.
const fs = require('fs');
const path = require('path');
const file = path.join(__dirname, '..', '.env');
if (fs.existsSync(file)) {
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) continue;
    const i = line.indexOf('=');
    const k = line.slice(0, i).trim();
    const v = line.slice(i + 1).trim().replace(/^['"]|['"]$/g, '');
    if (!(k in process.env)) process.env[k] = v;
  }
}
