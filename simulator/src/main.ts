import { Renderer } from './renderer';
import { HardwareUI } from './hardware-ui';
import { StateInspector } from './state-inspector';

// Types shared between main thread and worker
export interface ButtonMessage {
  type: 'button';
  keyNumber: number;
  pressed: boolean;
}

export interface EncoderMessage {
  type: 'encoder';
  position: number;
}

export interface InitMessage {
  type: 'init';
  saves: Record<string, string>;
}

export type MainToWorker = ButtonMessage | EncoderMessage | InitMessage;

export interface RefreshMessage {
  type: 'refresh';
  sceneGraph: SceneNode[];
}

export interface StateMessage {
  type: 'state';
  mode: number;
  wpm: number;
  playing: boolean;
  finished: boolean;
  bookId: number;
  lineNum: number;
  wordIdx: number;
  themeIndex: number;
  brightness: number;
  bookTitle?: string;
  bookAuthor?: string;
  bookLen?: number;
}

export interface SaveMessage {
  type: 'save';
  filename: string;
  data: string;
}

export interface ConsoleMessage {
  type: 'console';
  message: string;
}

export interface ReadyMessage {
  type: 'ready';
}

export interface BrightnessMessage {
  type: 'brightness';
  value: number;
}

export type WorkerToMain =
  | RefreshMessage
  | StateMessage
  | SaveMessage
  | ConsoleMessage
  | ReadyMessage
  | BrightnessMessage;

// Scene graph node types
export interface TileGridNode {
  type: 'tilegrid';
  x: number;
  y: number;
  w: number;
  h: number;
  paletteColors: number[];
  bitmapData?: number[];
}

export interface LabelNode {
  type: 'label';
  text: string;
  x: number;
  y: number;
  anchorX: number;
  anchorY: number;
  color: number;
  fontId: string;
  baseAlignment: boolean;
}

export interface RectNode {
  type: 'rect';
  x: number;
  y: number;
  w: number;
  h: number;
  fill: number;
  outline: number;
  stroke: number;
}

export type SceneNode = TileGridNode | LabelNode | RectNode;

// ============================================================
// App bootstrap
// ============================================================

class App {
  private worker!: Worker;
  private renderer!: Renderer;
  private hardwareUI!: HardwareUI;
  private inspector!: StateInspector;

  async start() {
    const canvas = document.getElementById('lcd') as HTMLCanvasElement;
    this.renderer = new Renderer(canvas);
    this.inspector = new StateInspector();

    this.hardwareUI = new HardwareUI(
      (msg) => this.sendToWorker(msg),
    );

    this.startWorker();
  }

  private startWorker() {
    this.worker = new Worker(
      new URL('./worker.ts', import.meta.url),
      { type: 'module' },
    );

    this.worker.onmessage = (e: MessageEvent<WorkerToMain>) => {
      this.handleWorkerMessage(e.data);
    };

    this.worker.onerror = (e) => {
      this.inspector.logError(`Worker error: ${e.message}`);
    };

    // Load saves from localStorage and send init
    const saves: Record<string, string> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith('picoReader_save_')) {
        const filename = key.slice('picoReader_save_'.length);
        saves[filename] = localStorage.getItem(key)!;
      }
    }
    this.sendToWorker({ type: 'init', saves });
  }

  private sendToWorker(msg: MainToWorker) {
    this.worker?.postMessage(msg);
  }

  private handleWorkerMessage(msg: WorkerToMain) {
    switch (msg.type) {
      case 'refresh':
        this.renderer.renderScene(msg.sceneGraph);
        this.inspector.updateGroupTree(msg.sceneGraph);
        break;

      case 'state':
        this.inspector.updateState(msg);
        break;

      case 'save':
        localStorage.setItem(`picoReader_save_${msg.filename}`, msg.data);
        break;

      case 'console':
        this.inspector.log(msg.message);
        break;

      case 'ready':
        document.getElementById('loading-overlay')?.classList.add('hidden');
        this.inspector.log('Pyodide ready, starting code_v2.py...');
        break;

      case 'brightness': {
        const overlay = document.getElementById('backlight-overlay')!;
        overlay.style.opacity = String(1 - msg.value / 100);
        this.inspector.updateBrightness(msg.value);
        break;
      }
    }
  }
}

const app = new App();
app.start();
