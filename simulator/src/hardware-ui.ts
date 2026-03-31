import type { MainToWorker } from './main';

export class HardwareUI {
  private sendMessage: (msg: MainToWorker) => void;
  private encoderPosition = 0;
  private isDragging = false;
  private lastAngle = 0;

  constructor(sendMessage: (msg: MainToWorker) => void) {
    this.sendMessage = sendMessage;
    this.setupButtons();
    this.setupClickwheel();
    this.setupKeyboard();
  }

  private setupButtons() {
    const buttons = document.querySelectorAll<HTMLElement>('.btn');
    buttons.forEach((btn) => {
      const keyNumber = parseInt(btn.dataset.key ?? '-1', 10);
      if (keyNumber < 0) return;

      const press = (e: Event) => {
        e.preventDefault();
        btn.classList.add('active');
        this.sendMessage({ type: 'button', keyNumber, pressed: true });
        setTimeout(() => btn.classList.remove('active'), 120);
      };

      btn.addEventListener('mousedown', press);
      btn.addEventListener('touchstart', press);
    });
  }

  private setupClickwheel() {
    const wheel = document.getElementById('clickwheel')!;
    const knob = document.getElementById('knob')!;

    const getAngle = (e: MouseEvent | Touch): number => {
      const rect = wheel.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      return Math.atan2(e.clientY - cy, e.clientX - cx);
    };

    const updateKnob = () => {
      const angle = (this.encoderPosition * 15) % 360;
      const rad = (angle * Math.PI) / 180;
      const kx = 50 + 42 * Math.sin(rad);
      const ky = 50 - 42 * Math.cos(rad);
      knob.setAttribute('cx', String(kx));
      knob.setAttribute('cy', String(ky));
    };

    // Mouse drag rotation
    wheel.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.lastAngle = getAngle(e);
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      const angle = getAngle(e);
      let delta = angle - this.lastAngle;

      // Normalize to [-PI, PI]
      if (delta > Math.PI) delta -= 2 * Math.PI;
      if (delta < -Math.PI) delta += 2 * Math.PI;

      // 15 degrees per step (0.2618 radians)
      const steps = Math.trunc(delta / 0.2618);
      if (steps !== 0) {
        this.encoderPosition += steps;
        this.sendMessage({ type: 'encoder', position: this.encoderPosition });
        this.lastAngle = angle;
        updateKnob();
      }
    });

    document.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    // Touch drag rotation
    wheel.addEventListener('touchstart', (e) => {
      this.isDragging = true;
      this.lastAngle = getAngle(e.touches[0]);
      e.preventDefault();
    });

    document.addEventListener('touchmove', (e) => {
      if (!this.isDragging) return;
      const angle = getAngle(e.touches[0]);
      let delta = angle - this.lastAngle;
      if (delta > Math.PI) delta -= 2 * Math.PI;
      if (delta < -Math.PI) delta += 2 * Math.PI;
      const steps = Math.trunc(delta / 0.2618);
      if (steps !== 0) {
        this.encoderPosition += steps;
        this.sendMessage({ type: 'encoder', position: this.encoderPosition });
        this.lastAngle = angle;
        updateKnob();
      }
    });

    document.addEventListener('touchend', () => {
      this.isDragging = false;
    });

    // Scroll wheel
    wheel.addEventListener('wheel', (e) => {
      e.preventDefault();
      const direction = e.deltaY > 0 ? 1 : -1;
      this.encoderPosition += direction;
      this.sendMessage({ type: 'encoder', position: this.encoderPosition });
      updateKnob();
    }, { passive: false });
  }

  private setupKeyboard() {
    const keyMap: Record<string, number> = {
      ' ': 0,           // CENTER
      'ArrowUp': 1,     // UP
      'ArrowLeft': 2,   // LEFT
      'ArrowRight': 3,  // RIGHT
      'ArrowDown': 4,   // DOWN
    };

    const encoderKeys: Record<string, number> = {
      '[': -1,
      ']': 1,
    };

    document.addEventListener('keydown', (e) => {
      // Don't capture if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      const keyNumber = keyMap[e.key];
      if (keyNumber !== undefined) {
        e.preventDefault();
        this.sendMessage({ type: 'button', keyNumber, pressed: true });

        // Visual feedback
        const btn = document.querySelector(`.btn[data-key="${keyNumber}"]`);
        btn?.classList.add('active');
        setTimeout(() => btn?.classList.remove('active'), 120);
        return;
      }

      const encDir = encoderKeys[e.key];
      if (encDir !== undefined) {
        e.preventDefault();
        this.encoderPosition += encDir;
        this.sendMessage({ type: 'encoder', position: this.encoderPosition });

        const knob = document.getElementById('knob')!;
        const angle = (this.encoderPosition * 15) % 360;
        const rad = (angle * Math.PI) / 180;
        knob.setAttribute('cx', String(50 + 42 * Math.sin(rad)));
        knob.setAttribute('cy', String(50 - 42 * Math.cos(rad)));
      }
    });
  }
}
