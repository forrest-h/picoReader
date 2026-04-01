import { defineConfig, Plugin } from 'vite';
import path from 'path';
import fs from 'fs';

// Serve ../firmware/ at /firmware/ so worker.ts can fetch code.py and pico_reader modules
function serveFirmware(): Plugin {
  const firmwareDir = path.resolve(__dirname, '../firmware');
  return {
    name: 'serve-firmware',
    configureServer(server) {
      server.middlewares.use('/firmware', (req, res, next) => {
        const filePath = path.join(firmwareDir, req.url ?? '');
        if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
          res.setHeader('Content-Type', 'text/plain');
          fs.createReadStream(filePath).pipe(res);
        } else {
          next();
        }
      });
    },
  };
}

export default defineConfig({
  root: '.',
  build: {
    outDir: 'dist',
  },
  plugins: [serveFirmware()],
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
    fs: {
      allow: ['.', path.resolve(__dirname, '../firmware')],
    },
  },
});
