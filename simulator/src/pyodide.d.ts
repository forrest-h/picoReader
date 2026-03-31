// Type declarations for Pyodide CDN import
declare module 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.mjs' {
  export function loadPyodide(options?: Record<string, unknown>): Promise<any>;
}
