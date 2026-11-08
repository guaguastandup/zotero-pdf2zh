"""Run the actual log-view script against a deterministic DOM/fetch clock."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest


class LogViewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_incremental_polling_and_controls(self):
        html = Path(__file__).parents[1].joinpath('index.html').read_text(encoding='utf-8')
        script = re.search(r'<script id="log-view-script">(.*?)</script>', html, re.S).group(1)
        harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const elements = {};
for (const id of ['logOutput', 'logStatus', 'logPause', 'logInterval', 'logIntervalDisplay']) {
  elements[id] = {textContent: '', value: '200', scrollHeight: 99, listeners: {},
    addEventListener(type, fn) {this.listeners[type] = fn;}, setAttribute() {}};
}
let nextId = 0, pending = [], calls = [], timers = new Map();
let storedInterval = null, storageFails = false;
const context = {localStorage: {getItem() {if (storageFails) throw new Error('denied'); return storedInterval;}, setItem(key, value) {if(storageFails) throw new Error('denied'); storedInterval = value;}}, document: {getElementById: id => elements[id]}, window: {addEventListener() {}},
  AbortController, Number, String, Error,
  setTimeout(fn, delay) {timers.set(++nextId, {fn, delay}); return nextId;},
  clearTimeout(id) {timers.delete(id);},
  fetch(url, options) {calls.push({url, options}); return new Promise((resolve, reject) => pending.push({resolve, reject}));}
};
vm.createContext(context);
vm.runInContext(SCRIPT + '\n globalThis.viewer = logViewer;', context);
const tick = async () => {for(let i=0;i<8;i++) await Promise.resolve();};
const reply = async data => {pending.shift().resolve({ok:true, json:async()=>({cursor: 'stable/token +&?', ...data})}); await tick();};
const poll = async () => {const entry = [...timers].find(([,v])=>v.delay!==10000); assert.ok(entry); timers.delete(entry[0]); entry[1].fn(); await tick();};
(async () => {
  context.viewer.start(); context.viewer.start();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/logs?offset=0&cursor=');
  assert.equal(calls[0].options.mode, 'same-origin');
  await reply({text:'<img onerror=alert(1)>', offset:25, reset:false});
  assert.equal(elements.logOutput.textContent, '<img onerror=alert(1)>');
  assert.equal(elements.logOutput.scrollTop, 99);
  assert.ok([...timers.values()].some(v=>v.delay===200));
  await poll(); assert.equal(calls[1].url, '/api/logs?offset=25&cursor=stable%2Ftoken%20%2B%26%3F');
  await reply({text:'x'.repeat(210000), offset:210025, reset:false});
  assert.equal(elements.logOutput.textContent.length, 200000);
  await poll(); await reply({text:'\u001b[31mold\rnew\u001b[0m', offset:3, reset:true});
  assert.equal(elements.logOutput.textContent, 'new');
  await poll(); await reply({text:'\u001b[3', offset:6, reset:false});
  assert.equal(elements.logOutput.textContent, 'new');
  await poll(); await reply({text:'2m\rnext\r\nline', offset:20, reset:false});
  assert.equal(elements.logOutput.textContent, 'next\nline');
  await poll(); await reply({text:'new', offset:3, reset:true, cursor:'rotated/token'});
  await poll();
  elements.logPause.listeners.click();
  assert.ok(calls.at(-1).options.signal.aborted);
  elements.logPause.listeners.click();
  const before = calls.length;
  await reply({text:'stale', offset:8, reset:true, cursor:'stale-token'});
  assert.equal(elements.logOutput.textContent, 'new');
  assert.equal(calls.length, before);
  await poll(); assert.equal(calls.at(-1).url, '/api/logs?offset=3&cursor=rotated%2Ftoken');
  pending.shift().reject(new Error('offline')); await tick();
  assert.match(elements.logStatus.textContent, /offline/);
  await poll(); await reply({text:'', offset:0, reset:true, cursor:''});
  assert.match(elements.logStatus.textContent, /暂无日志/);
  elements.logInterval.value='5'; elements.logInterval.listeners.change();
  assert.equal(elements.logInterval.value, '100');
  assert.ok([...timers.values()].some(v=>v.delay===100));
  await poll();
  assert.equal(calls.at(-1).url, '/api/logs?offset=0&cursor=');
  pending.shift().resolve({ok:false,status:503,json:async()=>({error:'Background logging is not enabled'})});
  await tick();
  assert.match(elements.logStatus.textContent, /后台启动模式/);
  assert.match(elements.logStatus.textContent, /Background logging is not enabled/);
  context.viewer.stop(); assert.equal(timers.size,0);
  assert.equal(storedInterval, '100');
  vm.runInContext('globalThis.restored = createLogViewer(document.getElementById("logOutput"), document.getElementById("logStatus"), document.getElementById("logPause"), document.getElementById("logInterval"));', context);
  assert.equal(elements.logInterval.value, '100');
  storedInterval = '60001';
  vm.runInContext('globalThis.invalid = createLogViewer(document.getElementById("logOutput"), document.getElementById("logStatus"), document.getElementById("logPause"), document.getElementById("logInterval"));', context);
  assert.equal(elements.logInterval.value, '200');
  storageFails = true;
  vm.runInContext('globalThis.blocked = createLogViewer(document.getElementById("logOutput"), document.getElementById("logStatus"), document.getElementById("logPause"), document.getElementById("logInterval"));', context);
  assert.equal(elements.logInterval.value, '200');
  elements.logInterval.value='1000'; elements.logInterval.listeners.change();
  assert.equal(elements.logInterval.value, '200');
  context.blocked.stop(); context.invalid.stop(); context.restored.stop();
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', harness.replace('SCRIPT', json.dumps(script))], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
