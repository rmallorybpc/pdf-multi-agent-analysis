#!/usr/bin/env node

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const pdf = require('pdf-parse');

const ROOT = process.cwd();
const INPUT_ROOT = path.join(ROOT, 'rfp-pdfs');
const OUTPUT_ROOT = path.join(ROOT, 'rfp-markdown');

function parseArgs(argv) {
  const args = {
    ocrFallback: false,
    minTextChars: 400,
    inputPath: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--ocr-fallback') {
      args.ocrFallback = true;
    } else if (token === '--min-text-chars') {
      const next = argv[i + 1];
      if (!next) {
        throw new Error('--min-text-chars requires a numeric value');
      }
      args.minTextChars = Number(next);
      if (!Number.isFinite(args.minTextChars) || args.minTextChars < 0) {
        throw new Error('--min-text-chars must be a non-negative number');
      }
      i += 1;
    } else if (token.startsWith('--')) {
      throw new Error(`Unknown option: ${token}`);
    } else if (!args.inputPath) {
      args.inputPath = token;
    } else {
      throw new Error(`Unexpected positional argument: ${token}`);
    }
  }

  return args;
}

function walkPdfFiles(dir, out = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const abs = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkPdfFiles(abs, out);
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.pdf')) {
      out.push(abs);
    }
  }
  return out;
}

function normalizeMarkdown(text) {
  const cleaned = text
    .replace(/\r\n/g, '\n')
    .replace(/\u0000/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  if (!cleaned) {
    return '';
  }

  const blocks = cleaned.split(/\n\n+/).map((block) => block.replace(/\n/g, ' ').replace(/[ ]+/g, ' ').trim());
  return `${blocks.filter(Boolean).join('\n\n')}\n`;
}

function commandExists(cmd) {
  const result = spawnSync('bash', ['-lc', `command -v ${cmd}`], { stdio: 'pipe', encoding: 'utf-8' });
  return result.status === 0;
}

function runOcr(pdfPath) {
  if (!commandExists('pdftoppm') || !commandExists('tesseract')) {
    return { text: '', available: false };
  }

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pdf-ocr-'));
  const imagePrefix = path.join(tempDir, 'page');
  const ppm = spawnSync('pdftoppm', ['-png', pdfPath, imagePrefix], { stdio: 'pipe', encoding: 'utf-8' });

  if (ppm.status !== 0) {
    fs.rmSync(tempDir, { recursive: true, force: true });
    return { text: '', available: true, error: ppm.stderr || 'pdftoppm failed' };
  }

  const pages = fs
    .readdirSync(tempDir)
    .filter((f) => f.endsWith('.png'))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

  const chunks = [];
  for (const page of pages) {
    const img = path.join(tempDir, page);
    const tesseract = spawnSync('tesseract', [img, 'stdout', '-l', 'eng'], { stdio: 'pipe', encoding: 'utf-8' });
    if (tesseract.status === 0) {
      chunks.push(tesseract.stdout || '');
    }
  }

  fs.rmSync(tempDir, { recursive: true, force: true });
  return { text: chunks.join('\n\n').trim(), available: true };
}

function toFrontmatter({ title, sourcePath, pageCount, extractionMethod }) {
  return [
    '---',
    `title: "${title.replace(/"/g, '\\"')}"`,
    `source_path: "${sourcePath.replace(/"/g, '\\"')}"`,
    `page_count: ${pageCount}`,
    `extraction_method: "${extractionMethod}"`,
    '---',
    '',
  ].join('\n');
}

async function extractPdf(pdfPath, options) {
  const buffer = fs.readFileSync(pdfPath);
  const native = await pdf(buffer);
  const nativeText = (native.text || '').trim();

  let finalText = nativeText;
  let extractionMethod = 'native';

  if (options.ocrFallback && nativeText.length < options.minTextChars) {
    const ocr = runOcr(pdfPath);
    if (ocr.available && ocr.text.length > finalText.length) {
      finalText = ocr.text;
      extractionMethod = 'ocr';
    }
  }

  return {
    pageCount: native.numpages || 0,
    text: normalizeMarkdown(finalText),
    extractionMethod,
  };
}

function ensureParent(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function mapPdfToMarkdown(pdfPath) {
  const rel = path.relative(INPUT_ROOT, pdfPath);
  const outRel = rel.replace(/\.pdf$/i, '.md');
  return path.join(OUTPUT_ROOT, outRel);
}

function resolveTargets(inputPath) {
  if (!fs.existsSync(INPUT_ROOT)) {
    return [];
  }

  if (!inputPath) {
    return walkPdfFiles(INPUT_ROOT).sort();
  }

  const abs = path.isAbsolute(inputPath) ? inputPath : path.join(ROOT, inputPath);
  if (!fs.existsSync(abs)) {
    throw new Error(`Input path does not exist: ${inputPath}`);
  }

  const stat = fs.statSync(abs);
  if (stat.isDirectory()) {
    return walkPdfFiles(abs).sort();
  }
  if (stat.isFile() && abs.toLowerCase().endsWith('.pdf')) {
    return [abs];
  }

  throw new Error(`Input path must be a PDF file or directory: ${inputPath}`);
}

async function convertOne(pdfPath, options) {
  if (!pdfPath.startsWith(INPUT_ROOT)) {
    throw new Error(`PDF must be under rfp-pdfs/: ${pdfPath}`);
  }

  const rel = path.relative(ROOT, pdfPath);
  const title = path.basename(pdfPath, path.extname(pdfPath));
  const target = mapPdfToMarkdown(pdfPath);
  const extraction = await extractPdf(pdfPath, options);
  const frontmatter = toFrontmatter({
    title,
    sourcePath: rel,
    pageCount: extraction.pageCount,
    extractionMethod: extraction.extractionMethod,
  });
  const body = extraction.text || '_No text extracted from PDF._\n';
  const next = `${frontmatter}${body}`;

  let changed = true;
  if (fs.existsSync(target)) {
    const current = fs.readFileSync(target, 'utf-8');
    changed = current !== next;
  }

  if (changed) {
    ensureParent(target);
    fs.writeFileSync(target, next, 'utf-8');
  }

  return {
    pdf: pdfPath,
    markdown: target,
    changed,
    extractionMethod: extraction.extractionMethod,
    chars: extraction.text.length,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const targets = resolveTargets(args.inputPath);

  if (targets.length === 0) {
    console.log('No PDFs found under rfp-pdfs/.');
    return;
  }

  const results = [];
  for (const pdfPath of targets) {
    const result = await convertOne(pdfPath, args);
    results.push(result);
    const relOut = path.relative(ROOT, result.markdown);
    const relIn = path.relative(ROOT, result.pdf);
    if (result.changed) {
      console.log(`converted: ${relIn} -> ${relOut} [${result.extractionMethod}, chars=${result.chars}]`);
    } else {
      console.log(`unchanged: ${relIn} -> ${relOut} [${result.extractionMethod}, chars=${result.chars}]`);
    }
  }

  const changed = results.filter((r) => r.changed).length;
  console.log(`done: total=${results.length}, changed=${changed}, unchanged=${results.length - changed}`);
}

main().catch((err) => {
  console.error(`conversion error: ${err.message}`);
  process.exit(1);
});
