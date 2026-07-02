import express from 'express';
import cors from 'cors';
import { exec } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(cors());
app.use(express.json());

const portfolioPath = path.resolve(__dirname, '../data/portfolio.json');

// --- Global Update Progress State ---
let updateStatus = {
  status: 'idle', // 'idle' | 'updating' | 'success' | 'error'
  progress: 0,
  currentStep: '',
  error: null,
  lastUpdated: new Date().toISOString()
};

function setStatus(status, progress, currentStep, error = null) {
  updateStatus = {
    status,
    progress,
    currentStep,
    error,
    lastUpdated: new Date().toISOString()
  };
  console.log(`[UpdateStatus] status=${status}, progress=${progress}%, step="${currentStep}"`);
}

function loadEnvFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const content = fs.readFileSync(filePath, 'utf8');
  const envs = {};
  content.split('\n').forEach(line => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) return;
    const match = trimmed.match(/^(?:export\s+)?([\w.-]+)\s*=\s*(.*)$/);
    if (match) {
      let val = match[2].trim();
      if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
      if (val.startsWith("'") && val.endsWith("'")) val = val.slice(1, -1);
      envs[match[1]] = val;
    }
  });
  return envs;
}

async function runUpdateSequence() {
  setStatus('updating', 5, '準備啟動更新管線...');
  
  const cwd = path.resolve(__dirname, '../');
  const pythonBin = '/Library/Frameworks/Python.framework/Versions/3.14/bin/python3';

  // Load Env variables dynamically to pass to child processes
  const env = { ...process.env };
  const secretsPath = path.resolve(cwd, 'secrets-local/finmind.env');
  const dotEnvPath = path.resolve(cwd, '.env');
  
  let loadedEnv = {};
  if (fs.existsSync(secretsPath)) {
    loadedEnv = loadEnvFile(secretsPath);
    console.log('Loaded env from secrets-local/finmind.env');
  } else if (fs.existsSync(dotEnvPath)) {
    loadedEnv = loadEnvFile(dotEnvPath);
    console.log('Loaded env from .env');
  }
  Object.assign(env, loadedEnv);

  const steps = [
    { script: 'scripts/fetch_official_classification.py', progress: 15, name: '更新 TWSE/TPEX 官方產業分類...' },
    { script: 'scripts/update_daily.py', progress: 40, name: '下載官方每日價格與法人金流數據...' },
    { script: 'scripts/update_txf_after_hours.py', progress: 50, name: '更新台指期夜盤資料...' },
    { script: 'scripts/fetch_global_news.py', progress: 60, name: '拉取國際財經重要新聞...' },
    { script: 'scripts/fetch_sectorrotation_reference.py', progress: 70, name: '拉取市場板塊輪動對照指標...' },
    { script: 'scripts/fetch_financial_statements.py', progress: 80, name: '更新基本面財務季報數據...' },
    { script: 'scripts/fetch_sentiment_and_macro.py', progress: 90, name: '更新新聞情緒與大盤風險狀態...' },
    { script: 'scripts/build_formal_json_outputs.py', progress: 100, name: '重新編譯產出前端儀表板 JSON 緩存...' }
  ];

  try {
    for (const step of steps) {
      setStatus('updating', updateStatus.progress, step.name);
      
      const scriptPath = path.resolve(cwd, step.script);
      console.log(`Executing step: ${step.script}`);
      
      await new Promise((resolve, reject) => {
        exec(`"${pythonBin}" "${scriptPath}"`, { cwd, env, maxBuffer: 1024 * 1024 * 10 }, (error, stdout, stderr) => {
          if (error) {
            console.error(`Step ${step.script} failed with error:`, error);
            console.error(stderr);
            reject(new Error(`步驟 ${step.script} 執行失敗`));
          } else {
            resolve();
          }
        });
      });
      
      setStatus('updating', step.progress, `${step.name} 完成`);
    }
    
    setStatus('success', 100, '台股資金板塊輪動數據更新成功！');
    
    // Automatically reset status back to idle after a delay so subsequent runs can trigger
    setTimeout(() => {
      if (updateStatus.status === 'success') {
        setStatus('idle', 0, '準備就緒');
      }
    }, 10000);

  } catch (err) {
    setStatus('error', updateStatus.progress, `更新失敗: ${err.message}`, err.message);
  }
}

// --- Endpoints ---

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

app.get('/api/update-status', (req, res) => {
  res.json(updateStatus);
});

app.post('/api/update', (req, res) => {
  if (updateStatus.status === 'updating') {
    return res.status(400).json({ status: 'error', message: 'Update already in progress' });
  }
  
  console.log('Received manual update request. Starting asynchronous sequence...');
  res.json({ status: 'started' });

  runUpdateSequence().catch(err => {
    console.error('Fatal error in background update sequence:', err);
  });
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
});
