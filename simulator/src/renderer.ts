import type { SceneNode, TileGridNode, LabelNode, RectNode } from './main';
import type { PcfFont } from './pcf-parser';
import { parsePcfFont, getStringWidth } from './pcf-parser';

const DISPLAY_WIDTH = 160;
const DISPLAY_HEIGHT = 128;

function bgrToRgb(bgr: number): [number, number, number] {
  return [bgr & 0xff, (bgr >> 8) & 0xff, (bgr >> 16) & 0xff];
}

export class Renderer {
  private ctx: CanvasRenderingContext2D;
  private imageData: ImageData;
  private fonts: Map<string, PcfFont> = new Map();

  constructor(canvas: HTMLCanvasElement) {
    canvas.width = DISPLAY_WIDTH;
    canvas.height = DISPLAY_HEIGHT;
    this.ctx = canvas.getContext('2d', { willReadFrequently: true })!;
    this.imageData = this.ctx.createImageData(DISPLAY_WIDTH, DISPLAY_HEIGHT);
    this.loadFonts();
  }

  private async loadFonts() {
    const fontFiles = [
      { id: 'fonts/Toronto_14.pcf', url: '/assets/fonts/Toronto_14.pcf' },
      { id: 'fonts/Toronto_9.pcf', url: '/assets/fonts/Toronto_9.pcf' },
    ];
    for (const { id, url } of fontFiles) {
      try {
        const resp = await fetch(url);
        const buf = await resp.arrayBuffer();
        const font = parsePcfFont(buf);
        this.fonts.set(id, font);
      } catch (e) {
        console.error(`Failed to load font ${id}:`, e);
      }
    }
  }

  renderScene(nodes: SceneNode[]) {
    // Clear to black
    const data = this.imageData.data;
    data.fill(0);
    for (let i = 3; i < data.length; i += 4) {
      data[i] = 255; // alpha
    }

    for (const node of nodes) {
      switch (node.type) {
        case 'tilegrid':
          this.renderTileGrid(node);
          break;
        case 'label':
          this.renderLabel(node);
          break;
        case 'rect':
          this.renderRect(node);
          break;
      }
    }

    this.ctx.putImageData(this.imageData, 0, 0);
  }

  private setPixel(x: number, y: number, r: number, g: number, b: number) {
    if (x < 0 || x >= DISPLAY_WIDTH || y < 0 || y >= DISPLAY_HEIGHT) return;
    const idx = (y * DISPLAY_WIDTH + x) * 4;
    this.imageData.data[idx] = r;
    this.imageData.data[idx + 1] = g;
    this.imageData.data[idx + 2] = b;
    this.imageData.data[idx + 3] = 255;
  }

  private fillRect(x: number, y: number, w: number, h: number, bgr: number) {
    const [r, g, b] = bgrToRgb(bgr);
    for (let py = y; py < y + h; py++) {
      for (let px = x; px < x + w; px++) {
        this.setPixel(px, py, r, g, b);
      }
    }
  }

  private renderTileGrid(node: TileGridNode) {
    if (node.bitmapData && node.bitmapData.length > 0) {
      // Per-pixel bitmap rendering (e.g., progress bar)
      for (let py = 0; py < node.h; py++) {
        for (let px = 0; px < node.w; px++) {
          const idx = py * node.w + px;
          const colorIdx = node.bitmapData[idx] ?? 0;
          const bgr = node.paletteColors[colorIdx] ?? 0;
          const [r, g, b] = bgrToRgb(bgr);
          this.setPixel(node.x + px, node.y + py, r, g, b);
        }
      }
    } else {
      // Solid fill with first palette color
      const bgr = node.paletteColors[0] ?? 0;
      this.fillRect(node.x, node.y, node.w, node.h, bgr);
    }
  }

  private renderLabel(node: LabelNode) {
    const font = this.fonts.get(node.fontId);
    if (!font) return;

    const [r, g, b] = bgrToRgb(node.color);
    const text = node.text;

    // Compute bounding box for anchor positioning
    const strWidth = getStringWidth(font, text);
    const strHeight = font.ascent + font.descent;

    // CircuitPython anchor math
    const drawX = Math.round(node.x - node.anchorX * strWidth);
    let drawY: number;
    if (node.baseAlignment) {
      // base_alignment=True: anchor Y=1.0 aligns to baseline
      drawY = Math.round(node.y - node.anchorY * font.ascent);
    } else {
      // base_alignment=False: anchor Y references full bounding box
      drawY = Math.round(node.y - node.anchorY * strHeight);
    }

    // Render each glyph
    let cursorX = drawX;
    for (let i = 0; i < text.length; i++) {
      const code = text.charCodeAt(i);
      const glyph = font.glyphs.get(code);
      if (!glyph) {
        cursorX += font.defaultAdvance;
        continue;
      }

      // Draw the glyph bitmap
      const gx = cursorX + glyph.xOffset;
      const gy = drawY + font.ascent - glyph.yOffset;

      for (let row = 0; row < glyph.height; row++) {
        for (let col = 0; col < glyph.width; col++) {
          const byteIdx = row * glyph.rowBytes + (col >> 3);
          const bitIdx = 7 - (col & 7);
          if (glyph.bitmap[byteIdx] & (1 << bitIdx)) {
            this.setPixel(gx + col, gy + row, r, g, b);
          }
        }
      }

      cursorX += glyph.advance;
    }
  }

  private renderRect(node: RectNode) {
    // Fill
    if (node.fill !== -1) {
      this.fillRect(node.x, node.y, node.w, node.h, node.fill);
    }

    // Outline
    if (node.outline !== -1 && node.stroke > 0) {
      const [r, g, b] = bgrToRgb(node.outline);
      for (let s = 0; s < node.stroke; s++) {
        // Top and bottom edges
        for (let px = node.x + s; px < node.x + node.w - s; px++) {
          this.setPixel(px, node.y + s, r, g, b);
          this.setPixel(px, node.y + node.h - 1 - s, r, g, b);
        }
        // Left and right edges
        for (let py = node.y + s; py < node.y + node.h - s; py++) {
          this.setPixel(node.x + s, py, r, g, b);
          this.setPixel(node.x + node.w - 1 - s, py, r, g, b);
        }
      }
    }
  }
}
