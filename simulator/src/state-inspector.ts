import type { StateMessage, SceneNode } from './main';

const MODE_NAMES = ['MENU', 'READER', 'DISPLAY'];

export class StateInspector {
  private consoleEl: HTMLElement;
  private maxConsoleLines = 200;

  constructor() {
    this.consoleEl = document.getElementById('insp-console')!;
  }

  updateState(msg: StateMessage) {
    this.setText('insp-mode', MODE_NAMES[msg.mode] ?? `MODE_${msg.mode}`);
    this.setText('insp-wpm', String(msg.wpm));

    let stateText = 'Paused';
    if (msg.finished) stateText = 'Finished';
    else if (msg.playing) stateText = 'Playing';
    this.setText('insp-playing', stateText);

    if (msg.bookTitle) this.setText('insp-title', msg.bookTitle);
    if (msg.bookAuthor) this.setText('insp-author', msg.bookAuthor);

    this.setText('insp-line', `${msg.lineNum} / ${msg.bookLen ?? '?'}`);
    this.setText('insp-word', String(msg.wordIdx));

    // Theme color swatches
    const THEMES = [
      [0x000000, 0xe7e7e7, 0x4c4c4c, 0x7c7c7c],
      [0xf3f3f3, 0x000000, 0xa1a1a1, 0x949494],
      [0x696969, 0x000000, 0x272727, 0x403f3f],
      [0x460808, 0xbdbdbd, 0x898888, 0x0e8ee6],
      [0x000000, 0x696969, 0x4c4c4c, 0x696969],
    ];
    const theme = THEMES[msg.themeIndex] ?? THEMES[0];
    const swatchIds = ['swatch-bg', 'swatch-text', 'swatch-wpm', 'swatch-hl'];
    theme.forEach((bgr, i) => {
      const el = document.getElementById(swatchIds[i]);
      if (el) {
        const r = bgr & 0xff;
        const g = (bgr >> 8) & 0xff;
        const b = (bgr >> 16) & 0xff;
        el.style.background = `rgb(${r},${g},${b})`;
      }
    });
  }

  updateBrightness(value: number) {
    this.setText('insp-brightness', `${value}%`);
  }

  updateGroupTree(nodes: SceneNode[]) {
    const el = document.getElementById('insp-group-tree')!;
    // Clear existing content safely
    while (el.firstChild) el.removeChild(el.firstChild);

    const header = document.createElement('span');
    header.textContent = 'Group (root)';
    header.style.color = '#7aa2f7';
    el.appendChild(header);

    nodes.forEach((node, i) => {
      let desc = '';
      switch (node.type) {
        case 'tilegrid':
          desc = `TileGrid ${node.w}x${node.h}` +
            (node.bitmapData ? ' [bitmap]' : ' [solid]');
          break;
        case 'label':
          desc = `Label "${node.text.trim().slice(0, 16)}"`;
          break;
        case 'rect':
          desc = `Rect ${node.w}x${node.h} @(${node.x},${node.y})`;
          break;
      }

      const div = document.createElement('div');
      div.className = 'tree-node';

      const idx = document.createTextNode(`[${i}] `);
      div.appendChild(idx);

      const typeSpan = document.createElement('span');
      typeSpan.className = 'tree-label';
      typeSpan.textContent = node.type;
      div.appendChild(typeSpan);

      const descSpan = document.createElement('span');
      descSpan.className = 'tree-prop';
      descSpan.textContent = ` ${desc}`;
      div.appendChild(descSpan);

      el.appendChild(div);
    });
  }

  log(message: string) {
    const line = document.createElement('div');
    line.className = 'log-line';
    line.textContent = message;
    this.consoleEl.appendChild(line);
    this.trimConsole();
    this.consoleEl.scrollTop = this.consoleEl.scrollHeight;
  }

  logError(message: string) {
    const line = document.createElement('div');
    line.className = 'log-line log-error';
    line.textContent = message;
    this.consoleEl.appendChild(line);
    this.trimConsole();
    this.consoleEl.scrollTop = this.consoleEl.scrollHeight;
  }

  private setText(id: string, text: string) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  private trimConsole() {
    while (this.consoleEl.children.length > this.maxConsoleLines) {
      this.consoleEl.removeChild(this.consoleEl.firstChild!);
    }
  }
}
