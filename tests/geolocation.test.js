// Story 10, browser side: geolocation/index.html against fake browser APIs.
// Run: node --test tests/geolocation.test.js
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "..", "geolocation", "index.html"), "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

// Loads the component with `geolocation(ok, err)` playing the browser's answer
// (undefined = the browser has no geolocation API). Returns what it sends to Streamlit.
function mount(geolocation) {
  const sent = [], listeners = [], asked = [];
  const window = {
    parent: {postMessage: (message) => sent.push(message)},
    addEventListener: (type, f) => listeners.push(f),
    removeEventListener: (type, f) => listeners.splice(listeners.indexOf(f), 1),
  };
  const navigator = geolocation === undefined ? {} : {
    geolocation: {getCurrentPosition: (ok, err, options) => { asked.push(options); geolocation(ok, err); }},
  };
  new Function("window", "navigator", script)(window, navigator);
  const render = () => [...listeners].forEach((f) => f({data: {type: "streamlit:render", args: {}}}));
  const values = () => sent.filter((m) => m.type === "streamlit:setComponentValue").map((m) => m.value);
  return {sent, asked, render, values};
}

const atOffice = (ok) => ok({coords: {latitude: 32.6615, longitude: 35.1062, accuracy: 12}});

test("tells Streamlit it is ready and takes no space", () => {
  const c = mount(atOffice);
  assert.deepStrictEqual(c.sent, [
    {isStreamlitMessage: true, type: "streamlit:componentReady", apiVersion: 1},
    {isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 0},
  ]);
});

test("asks for a fresh, precise location once shown, and sends it as JSON", () => {
  const c = mount(atOffice);
  assert.deepStrictEqual(c.asked, []);
  c.render();
  assert.deepStrictEqual(c.asked, [{enableHighAccuracy: true, timeout: 20000, maximumAge: 0}]);
  assert.deepStrictEqual(c.values(), [{lat: 32.6615, lon: 35.1062, accuracy: 12}]);
  assert.strictEqual(c.sent.at(-1).dataType, "json");
});

test("asks only once while the board refreshes", () => {
  const c = mount(atOffice);
  c.render(); c.render(); c.render();
  assert.strictEqual(c.asked.length, 1);
  assert.strictEqual(c.values().length, 1);
});

test("reports a refused or failed location as {error}", () => {
  let c = mount((ok, err) => err({code: 1, message: "User denied Geolocation"}));
  c.render();
  assert.deepStrictEqual(c.values(), [{error: "User denied Geolocation"}]);
  c = mount((ok, err) => err({code: 3, message: ""}));
  c.render();
  assert.deepStrictEqual(c.values(), [{error: "location unavailable"}]);
});

test("reports a browser without location support", () => {
  const c = mount(undefined);
  c.render();
  assert.deepStrictEqual(c.values(), [{error: "this browser can't share its location"}]);
});
