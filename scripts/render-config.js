#!/usr/bin/env node
'use strict';
/*
 * render-config.js - dependency-free config-template renderer for Powerhouse.
 *
 * Modes:
 *   forward <tpl> <out> KEY=VAL ...  Replace every {{KEY}} with KEY's FIRST value,
 *                                    JSON-escaped so the result stays valid JSON.
 *                                    Validates JSON.parse and leftover tokens, writes <out>.
 *   reverse <in> <out> KEY=VAL ...   Replace every occurrence of any of KEY's values
 *                                    (raw / slash-normalized / JSON-escaped forms,
 *                                    longest value first) with {{KEY}}, writes <out>.
 *   diff <tpl> <out> KEY=VAL ...     Render in memory, compare with the existing <out>,
 *                                    print 'template: unchanged' or 'template: would update'.
 *
 * KEY may be repeated: forward uses the first value per key, reverse uses all values.
 * Exit codes: 0 success; 1 usage error, unreadable/writable file, invalid JSON,
 *             or leftover template tokens after render.
 */

const fs = require('fs');

function fail(msg) {
  console.error('[render-config] ' + msg);
  process.exit(1);
}

function jsonEscapeValue(value) {
  // JSON.stringify returns a quoted string; strip the quotes so the escaped body
  // can be inserted inside a JSON string that already has its own quotes.
  return JSON.stringify(value).slice(1, -1);
}

function slashify(value) {
  return value.replace(/\\/g, '/');
}

function parseArgs(argv) {
  const mode = argv[0];
  const input = argv[1];
  const output = argv[2];
  if (!mode || !input || !output) {
    fail('usage: render-config.js <forward|reverse|diff> <in> <out> [KEY=VAL ...]');
  }
  if (['forward', 'reverse', 'diff'].indexOf(mode) === -1) fail('unknown mode: ' + mode);
  const pairs = [];
  for (const arg of argv.slice(3)) {
    const eq = arg.indexOf('=');
    if (eq < 1) fail('bad KEY=VAL argument: ' + arg);
    pairs.push({ key: arg.slice(0, eq), value: arg.slice(eq + 1) });
  }
  return { mode: mode, input: input, output: output, pairs: pairs };
}

function renderForward(template, pairs) {
  const first = new Map();
  for (const pair of pairs) {
    if (!first.has(pair.key)) first.set(pair.key, pair.value);
  }
  let out = template;
  for (const [key, value] of first) {
    out = out.split('{{' + key + '}}').join(jsonEscapeValue(value));
  }
  if (out.includes('{{')) fail('leftover template token after render');
  try {
    JSON.parse(out);
  } catch (err) {
    fail('rendered output is not valid JSON: ' + err.message);
  }
  return out;
}

function renderReverse(text, pairs) {
  const entries = [];
  for (const pair of pairs) {
    const forms = new Set([
      pair.value,
      slashify(pair.value),
      jsonEscapeValue(pair.value),
      jsonEscapeValue(slashify(pair.value)),
    ]);
    for (const form of forms) {
      if (form) entries.push({ value: form, token: '{{' + pair.key + '}}' });
    }
  }
  entries.sort((a, b) => b.value.length - a.value.length);
  let out = text;
  for (const entry of entries) {
    out = out.split(entry.value).join(entry.token);
  }
  return out;
}

function read(path, label) {
  try {
    return fs.readFileSync(path, 'utf8');
  } catch (err) {
    fail('cannot read ' + label + ' (' + path + '): ' + err.message);
  }
}

function write(path, text) {
  try {
    fs.writeFileSync(path, text, 'utf8');
  } catch (err) {
    fail('cannot write ' + path + ': ' + err.message);
  }
}

const args = parseArgs(process.argv.slice(2));

if (args.mode === 'forward') {
  const rendered = renderForward(read(args.input, 'template'), args.pairs);
  write(args.output, rendered);
  console.log('rendered: ' + args.output);
} else if (args.mode === 'reverse') {
  const reversed = renderReverse(read(args.input, 'input'), args.pairs);
  write(args.output, reversed);
  console.log('reversed: ' + args.output);
} else {
  const rendered = renderForward(read(args.input, 'template'), args.pairs);
  let existing = null;
  try {
    existing = fs.readFileSync(args.output, 'utf8');
  } catch (err) {
    existing = null; // missing file counts as a change
  }
  console.log(existing === rendered ? 'template: unchanged' : 'template: would update');
}
