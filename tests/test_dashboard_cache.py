import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


def test_dashboard_loads_fresh_data_on_each_page_load() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the browser data loader test")
    source = Path("dashboard/app.js").read_text(encoding="utf-8")
    loader = re.search(
        r"const dataVersion = .*?\n\nasync function loadJson\(path\) \{.*?\n\}",
        source,
        re.DOTALL,
    )
    assert loader is not None
    script = """
const assert = require("node:assert/strict");
const vm = require("node:vm");
const calls = [];
function page(now) {
  const context = {
    URL,
    Date: { now: () => now },
    window: { location: { href: "https://example.com/dashboard/" } },
    fetch: async (url, options) => {
      calls.push({ url: new URL(url), options });
      return { ok: true, json: async () => ({ loaded: true }) };
    },
  };
  vm.createContext(context);
  vm.runInContext(SOURCE, context);
  return context;
}
(async () => {
  const first = page(1000);
  assert.equal((await first.loadJson("data/overview.json")).loaded, true);
  await first.loadJson("data/current_zones/11.geojson?region=11");
  const second = page(2000);
  await second.loadJson("data/overview.json");
  assert.equal(calls[0].url.pathname, "/dashboard/data/overview.json");
  assert.equal(calls[1].url.searchParams.get("region"), "11");
  assert.equal(calls[0].options.cache, "no-store");
  assert.equal(calls[0].url.searchParams.get("_refresh"),
               calls[1].url.searchParams.get("_refresh"));
  assert.notEqual(calls[0].url.href, calls[2].url.href);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    script = script.replace("SOURCE", json.dumps(loader.group(0)))
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
