import express from 'express';
import cors from 'cors';
import { exec } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());

import fs from 'fs';
const portfolioPath = path.resolve(__dirname, '../data/portfolio.json');

app.get('/api/portfolio', (req, res) => {
  if (fs.existsSync(portfolioPath)) {
    try {
      res.json(JSON.parse(fs.readFileSync(portfolioPath, 'utf8')));
    } catch {
      res.json([]);
    }
  } else {
    res.json([]);
  }
});

app.post('/api/portfolio', (req, res) => {
  fs.writeFileSync(portfolioPath, JSON.stringify(req.body, null, 2), 'utf8');
  res.json({ status: 'ok' });
});

app.post('/api/update', (req, res) => {
  console.log('Received manual update request. Triggering run_daily_update.sh...');
  
  // The script is in the root directory, one level up from web/
  const scriptPath = path.resolve(__dirname, '../scripts/run_daily_update.sh');
  const cwd = path.resolve(__dirname, '../');
  
  // Respond immediately so frontend doesn't timeout, but we could also wait
  // The python script might take a couple of minutes to run.
  // For simplicity, let's wait and respond. If it times out, we should send immediately.
  // We will stream response or just wait since this is a local tool.
  exec(`zsh ${scriptPath}`, { cwd, maxBuffer: 1024 * 1024 * 10 }, (error, stdout, stderr) => {
    if (error) {
      console.error(`Update script failed: ${error}`);
      return res.status(500).json({ status: 'error', message: error.message, stderr });
    }
    console.log('Update script completed successfully.');
    return res.json({ status: 'ok', message: 'Data updated successfully' });
  });
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
});
