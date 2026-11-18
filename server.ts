import express from 'express';
import { execFile } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;

app.use(express.json({ limit: '5mb' }));

function readJsonSafe(filePath: string): any {
  try {
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    }
  } catch {
    // ignore
  }
  return null;
}

function readTextSafe(filePath: string): string {
  try {
    if (fs.existsSync(filePath)) {
      return fs.readFileSync(filePath, 'utf-8');
    }
  } catch {
    // ignore
  }
  return '';
}

function getWorkspaceSnapshot() {
  const config = readJsonSafe(path.join(__dirname, 'config.json'));
  const state = readJsonSafe(path.join(__dirname, '.eventos', 'state.json'));
  const finalPlan = readJsonSafe(path.join(__dirname, 'out', 'final_plan.json'));
  const lastTrace = readTextSafe(path.join(__dirname, 'out', 'trace.txt'));
  const sessionTrace = readTextSafe(path.join(__dirname, 'out', 'session_trace.txt'));
  const reportHtml = readTextSafe(path.join(__dirname, 'out', 'report.html'));

  const packsDir = path.join(__dirname, 'tests', 'packs');
  const packs: Array<{ name: string; path: string; content: string }> = [];
  if (fs.existsSync(packsDir)) {
    const files = fs.readdirSync(packsDir).filter((f) => f.endsWith('.txt')).sort();
    for (const file of files) {
      const relPath = path.join('tests', 'packs', file);
      packs.push({
        name: file,
        path: relPath,
        content: readTextSafe(path.join(__dirname, relPath)),
      });
    }
  }

  return {
    config,
    state,
    finalPlan,
    lastTrace,
    sessionTrace,
    reportHtml,
    packs,
  };
}

function executePythonRun(
  targetFile: string
): Promise<{ stdout: string; stderr: string; exitCode: number; seconds: number }> {
  const startedAt = Date.now();
  return new Promise((resolve) => {
    execFile(
      'python3',
      ['run.py', targetFile],
      {
        cwd: __dirname,
        env: { ...process.env },
        timeout: 120000,
        maxBuffer: 10 * 1024 * 1024,
      },
      (error, stdout, stderr) => {
        const elapsed = Number(((Date.now() - startedAt) / 1000).toFixed(2));
        resolve({
          stdout: stdout || '',
          stderr: stderr || (error ? error.message : ''),
          exitCode: error && typeof (error as any).code === 'number' ? (error as any).code : 0,
          seconds: elapsed,
        });
      }
    );
  });
}

app.get('/api/state', (_req, res) => {
  res.json(getWorkspaceSnapshot());
});

app.post('/api/run', async (req, res) => {
  try {
    const { packPath, customContent, customFilename } = req.body || {};
    let targetFile = packPath;

    if (typeof customContent === 'string' && customContent.trim().length > 0) {
      const customDir = path.join(__dirname, '.eventos', 'inputs');
      fs.mkdirSync(customDir, { recursive: true });
      const safeName = (customFilename || 'custom_message.txt').replace(/[^a-zA-Z0-9._-]/g, '_');
      targetFile = path.join('.eventos', 'inputs', safeName);
      fs.writeFileSync(path.join(__dirname, targetFile), customContent, 'utf-8');
    }

    if (!targetFile) {
      res.status(400).json({ error: 'Missing packPath or customContent' });
      return;
    }

    const result = await executePythonRun(targetFile);
    const snapshot = getWorkspaceSnapshot();
    res.json({
      ...snapshot,
      terminalOutput: result.stdout,
      stderr: result.stderr,
      executionSeconds: result.seconds,
      commandExecuted: `python run.py ${targetFile}`,
    });
  } catch (err: any) {
    res.status(500).json({ error: err?.message || 'Execution failed' });
  }
});

app.post('/api/reset', (_req, res) => {
  try {
    const eventosDir = path.join(__dirname, '.eventos');
    const outDir = path.join(__dirname, 'out');
    if (fs.existsSync(eventosDir)) {
      fs.rmSync(eventosDir, { recursive: true, force: true });
    }
    if (fs.existsSync(outDir)) {
      fs.rmSync(outDir, { recursive: true, force: true });
    }
    res.json(getWorkspaceSnapshot());
  } catch (err: any) {
    res.status(500).json({ error: err?.message || 'Reset failed' });
  }
});

app.post('/api/config', (req, res) => {
  try {
    const current = readJsonSafe(path.join(__dirname, 'config.json')) || {};
    const { llm, policy } = req.body || {};
    const updated = {
      llm: { ...(current.llm || {}), ...(llm || {}) },
      policy: { ...(current.policy || {}), ...(policy || {}) },
    };
    fs.writeFileSync(path.join(__dirname, 'config.json'), JSON.stringify(updated, null, 2) + '\n', 'utf-8');
    res.json(getWorkspaceSnapshot());
  } catch (err: any) {
    res.status(500).json({ error: err?.message || 'Failed to update config.json' });
  }
});

app.get('/api/report', (_req, res) => {
  const reportPath = path.join(__dirname, 'out', 'report.html');
  if (fs.existsSync(reportPath)) {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.send(fs.readFileSync(reportPath, 'utf-8'));
  } else {
    res.status(404).send('<html><body><p>No report generated yet. Run a message pack first.</p></body></html>');
  }
});

async function startServer() {
  // Auto-run sample_pack.txt on startup if out/final_plan.json doesn't exist yet
  const planPath = path.join(__dirname, 'out', 'final_plan.json');
  const samplePack = path.join('tests', 'packs', 'sample_pack.txt');
  if (!fs.existsSync(planPath) && fs.existsSync(path.join(__dirname, samplePack))) {
    await executePythonRun(samplePack);
  }

  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`EventOS Server running on http://localhost:${PORT}`);
  });
}

startServer();
