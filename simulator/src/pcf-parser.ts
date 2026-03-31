// PCF (Portable Compiled Font) binary parser
// Ref: https://fontforge.org/docs/techref/pcf-format.html

export interface Glyph {
  width: number;
  height: number;
  xOffset: number;  // left side bearing
  yOffset: number;  // ascent offset (distance from top of glyph to font ascent line)
  advance: number;  // horizontal advance width
  rowBytes: number;  // bytes per row in bitmap
  bitmap: Uint8Array; // 1-bit packed glyph image, MSB first
}

export interface PcfFont {
  glyphs: Map<number, Glyph>; // charCode -> Glyph
  ascent: number;
  descent: number;
  defaultAdvance: number;
}

// PCF table types
const PCF_PROPERTIES = 1 << 0;
const PCF_ACCELERATORS = 1 << 1;
const PCF_METRICS = 1 << 2;
const PCF_BITMAPS = 1 << 3;
const PCF_INK_METRICS = 1 << 4;
const PCF_BDF_ENCODINGS = 1 << 5;
const PCF_SWIDTHS = 1 << 6;
const PCF_GLYPH_NAMES = 1 << 7;
const PCF_BDF_ACCELERATORS = 1 << 8;

// Format flags
const PCF_DEFAULT_FORMAT = 0x00000000;
const PCF_INKBOUNDS = 0x00000200;
const PCF_ACCEL_W_INKBOUNDS = 0x00000100;
const PCF_COMPRESSED_METRICS = 0x00000100;

const PCF_GLYPH_PAD_MASK = 3;
const PCF_BYTE_MASK = 1 << 2;
const PCF_BIT_MASK = 1 << 3;
const PCF_SCAN_UNIT_MASK = 0x30;

interface TocEntry {
  type: number;
  format: number;
  size: number;
  offset: number;
}

class PcfReader {
  private view: DataView;
  private data: Uint8Array;

  constructor(buffer: ArrayBuffer) {
    this.view = new DataView(buffer);
    this.data = new Uint8Array(buffer);
  }

  private isLittleEndian(format: number): boolean {
    return (format & PCF_BYTE_MASK) === 0;
  }

  private isMsbBitOrder(format: number): boolean {
    return (format & PCF_BIT_MASK) !== 0;
  }

  private getGlyphPad(format: number): number {
    return 1 << (format & PCF_GLYPH_PAD_MASK);
  }

  private readInt32(offset: number, le: boolean): number {
    return this.view.getInt32(offset, le);
  }

  private readUint32(offset: number, le: boolean): number {
    return this.view.getUint32(offset, le);
  }

  private readInt16(offset: number, le: boolean): number {
    return this.view.getInt16(offset, le);
  }

  private readUint16(offset: number, le: boolean): number {
    return this.view.getUint16(offset, le);
  }

  parse(): PcfFont {
    // Verify magic: "\1fcp"
    const magic = this.readUint32(0, true);
    if (magic !== 0x70636601) {
      throw new Error(`Invalid PCF magic: 0x${magic.toString(16)}`);
    }

    const tableCount = this.readInt32(4, true);
    const toc: TocEntry[] = [];
    for (let i = 0; i < tableCount; i++) {
      const base = 8 + i * 16;
      toc.push({
        type: this.readInt32(base, true),
        format: this.readInt32(base + 4, true),
        size: this.readInt32(base + 8, true),
        offset: this.readInt32(base + 12, true),
      });
    }

    const findTable = (type: number) => toc.find((t) => t.type === type);

    // Parse accelerators (for ascent/descent)
    let ascent = 10;
    let descent = 3;
    const accelTable = findTable(PCF_BDF_ACCELERATORS) ?? findTable(PCF_ACCELERATORS);
    if (accelTable) {
      const fmt = this.readUint32(accelTable.offset, true);
      const le = this.isLittleEndian(fmt);
      // Accelerator structure: format(4) + noOverlap(1) + constantMetrics(1) + terminalFont(1)
      // + constantWidth(1) + inkInside(1) + inkMetrics(1) + drawDirection(1) + padding(1)
      // + fontAscent(4) + fontDescent(4) + maxOverlap(4)
      ascent = this.readInt32(accelTable.offset + 12, le);
      descent = this.readInt32(accelTable.offset + 16, le);
    }

    // Parse metrics
    const metricsTable = findTable(PCF_METRICS);
    if (!metricsTable) throw new Error('No METRICS table found');

    const metricsFmt = this.readUint32(metricsTable.offset, true);
    const metricsLE = this.isLittleEndian(metricsFmt);
    const compressed = (metricsFmt & PCF_COMPRESSED_METRICS) !== 0;

    interface MetricEntry {
      leftBearing: number;
      rightBearing: number;
      width: number;
      ascent: number;
      descent: number;
    }

    const metrics: MetricEntry[] = [];
    let mOffset = metricsTable.offset + 4;

    if (compressed) {
      const count = this.readUint16(mOffset, metricsLE);
      mOffset += 2;
      for (let i = 0; i < count; i++) {
        metrics.push({
          leftBearing: this.data[mOffset] - 0x80,
          rightBearing: this.data[mOffset + 1] - 0x80,
          width: this.data[mOffset + 2] - 0x80,
          ascent: this.data[mOffset + 3] - 0x80,
          descent: this.data[mOffset + 4] - 0x80,
        });
        mOffset += 5;
      }
    } else {
      const count = this.readInt32(mOffset, metricsLE);
      mOffset += 4;
      for (let i = 0; i < count; i++) {
        metrics.push({
          leftBearing: this.readInt16(mOffset, metricsLE),
          rightBearing: this.readInt16(mOffset + 2, metricsLE),
          width: this.readInt16(mOffset + 4, metricsLE),
          ascent: this.readInt16(mOffset + 6, metricsLE),
          descent: this.readInt16(mOffset + 8, metricsLE),
        });
        mOffset += 12;
      }
    }

    // Parse bitmaps
    const bitmapTable = findTable(PCF_BITMAPS);
    if (!bitmapTable) throw new Error('No BITMAPS table found');

    const bmpFmt = this.readUint32(bitmapTable.offset, true);
    const bmpLE = this.isLittleEndian(bmpFmt);
    const glyphPad = this.getGlyphPad(bmpFmt);
    const msbBit = this.isMsbBitOrder(bmpFmt);

    let bOffset = bitmapTable.offset + 4;
    const glyphCount = this.readInt32(bOffset, bmpLE);
    bOffset += 4;

    const offsets: number[] = [];
    for (let i = 0; i < glyphCount; i++) {
      offsets.push(this.readInt32(bOffset, bmpLE));
      bOffset += 4;
    }

    // 4 bitmap sizes (for different padding)
    const bitmapSizes: number[] = [];
    for (let i = 0; i < 4; i++) {
      bitmapSizes.push(this.readInt32(bOffset, bmpLE));
      bOffset += 4;
    }

    const bitmapDataStart = bOffset;

    // Parse BDF encodings (char code -> glyph index)
    const encTable = findTable(PCF_BDF_ENCODINGS);
    if (!encTable) throw new Error('No BDF_ENCODINGS table found');

    const encFmt = this.readUint32(encTable.offset, true);
    const encLE = this.isLittleEndian(encFmt);
    let eOffset = encTable.offset + 4;

    const minCharOrByte2 = this.readInt16(eOffset, encLE);
    eOffset += 2;
    const maxCharOrByte2 = this.readInt16(eOffset, encLE);
    eOffset += 2;
    const minByte1 = this.readInt16(eOffset, encLE);
    eOffset += 2;
    const maxByte1 = this.readInt16(eOffset, encLE);
    eOffset += 2;
    const defaultChar = this.readInt16(eOffset, encLE);
    eOffset += 2;

    // Build charCode -> glyphIndex map
    const charToGlyph = new Map<number, number>();
    for (let byte1 = minByte1; byte1 <= maxByte1; byte1++) {
      for (let byte2 = minCharOrByte2; byte2 <= maxCharOrByte2; byte2++) {
        const glyphIdx = this.readUint16(eOffset, encLE);
        eOffset += 2;
        if (glyphIdx !== 0xffff) {
          const charCode = byte1 > 0 ? (byte1 << 8) | byte2 : byte2;
          charToGlyph.set(charCode, glyphIdx);
        }
      }
    }

    // Build glyphs
    const glyphs = new Map<number, Glyph>();
    let defaultAdvance = 8;

    for (const [charCode, glyphIdx] of charToGlyph) {
      if (glyphIdx >= metrics.length || glyphIdx >= glyphCount) continue;

      const m = metrics[glyphIdx];
      const glyphWidth = m.rightBearing - m.leftBearing;
      const glyphHeight = m.ascent + m.descent;

      if (glyphWidth <= 0 || glyphHeight <= 0) {
        // Space or empty glyph
        glyphs.set(charCode, {
          width: 0,
          height: 0,
          xOffset: 0,
          yOffset: 0,
          advance: m.width,
          rowBytes: 0,
          bitmap: new Uint8Array(0),
        });
        continue;
      }

      const rowBytes = Math.ceil(glyphWidth / (glyphPad * 8)) * glyphPad;
      const bmpOffset = bitmapDataStart + offsets[glyphIdx];

      // Extract bitmap data
      const bmpSize = rowBytes * glyphHeight;
      const bitmap = new Uint8Array(bmpSize);

      for (let i = 0; i < bmpSize; i++) {
        let byte = this.data[bmpOffset + i] ?? 0;
        if (!msbBit) {
          // Reverse bit order within each byte
          byte = ((byte & 0x01) << 7) | ((byte & 0x02) << 5) | ((byte & 0x04) << 3) |
                 ((byte & 0x08) << 1) | ((byte & 0x10) >> 1) | ((byte & 0x20) >> 3) |
                 ((byte & 0x40) >> 5) | ((byte & 0x80) >> 7);
        }
        bitmap[i] = byte;
      }

      glyphs.set(charCode, {
        width: glyphWidth,
        height: glyphHeight,
        xOffset: m.leftBearing,
        yOffset: m.ascent,
        advance: m.width,
        rowBytes,
        bitmap,
      });
    }

    // Find default advance from space character
    const spaceGlyph = glyphs.get(32);
    if (spaceGlyph) {
      defaultAdvance = spaceGlyph.advance;
    }

    return { glyphs, ascent, descent, defaultAdvance };
  }
}

export function parsePcfFont(buffer: ArrayBuffer): PcfFont {
  return new PcfReader(buffer).parse();
}

export function getStringWidth(font: PcfFont, text: string): number {
  let width = 0;
  for (let i = 0; i < text.length; i++) {
    const glyph = font.glyphs.get(text.charCodeAt(i));
    width += glyph ? glyph.advance : font.defaultAdvance;
  }
  return width;
}

export function getStringHeight(font: PcfFont): number {
  return font.ascent + font.descent;
}
