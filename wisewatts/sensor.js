// ws-sensors-cli.js
// Usage: node ws-sensors-cli.js
// Install dependency: npm i ws

const WebSocket = require('ws');
const readline = require('readline');

const DEFAULT_WS = 'ws://13.210.103.10:8000/ws/clients/';

let wsUrl = process.env.WS_URL || DEFAULT_WS;
let ws = null;
let reconnectDelay = 1000;
let reconnectTimer = null;
let manualDisconnect = false; // true if user requested disconnect
let showLog = true;
let filterId = ''; // when non-empty, only show updates for this sensor_id

const sensors = new Map(); // sensor_id -> { payload, lastSeen: Date }

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function log(...args) {
  if (showLog) console.log(...args);
}

function printHeader() {
  console.clear();
  console.log('=== WS Sensors CLI ===');
  console.log(`URL: ${wsUrl}`);
  console.log(`Connection: ${ws && ws.readyState === WebSocket.OPEN ? 'CONNECTED' : 'DISCONNECTED'}`);
  console.log(`Known sensors: ${sensors.size} | filter: ${filterId || 'none'} | log: ${showLog ? 'on' : 'off'}`);
  console.log('Commands: (c)onnect  (d)isconnect  (f)ilter <id|empty>  (l)og toggle  (u)rl <wsurl>  (q)uit');
  console.log('----------------------\n');
}

function printTable() {
  // prepare array for console.table
  const rows = [];
  for (const [id, info] of sensors.entries()) {
    if (filterId && String(id) !== String(filterId)) continue;
    rows.push({
      sensor_id: id,
      last_seen: info.lastSeen.toLocaleTimeString(),
      water_level_cm: info.payload.water_level_cm ?? '—',
      distance_cm: info.payload.distance_cm ?? info.payload.distance ?? '—',
      pump_on: typeof info.payload.pump_on !== 'undefined' ? info.payload.pump_on : '—',
      raw: JSON.stringify(info.payload)
    });
  }
  if (rows.length === 0) {
    console.log('(no sensor rows to show)');
  } else {
    console.table(rows);
  }
}

function makeOrUpdateSensor(sensorPayload) {
  const id = sensorPayload.sensor_id ?? sensorPayload.id ?? sensorPayload.name ?? ('unk-' + Math.random().toString(36).slice(2, 8));
  const now = new Date();
  sensors.set(id, { payload: sensorPayload, lastSeen: now });
  log(`Updated ${id} — pump_on:${sensorPayload.pump_on ?? 'n/a'} water:${sensorPayload.water_level_cm ?? 'n/a'}`);
  render();
}

function handlePayload(payload) {
  if (Array.isArray(payload)) {
    log(`Received array of ${payload.length} sensors`);
    payload.forEach(p => makeOrUpdateSensor(p));
  } else if (payload && typeof payload === 'object') {
    makeOrUpdateSensor(payload);
  } else {
    log('Unexpected payload type:', typeof payload);
  }
}

function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    console.log('Already connected.');
    return;
  }
  manualDisconnect = false;
  clearReconnectTimer();
  ws = new WebSocket(wsUrl);

  ws.on('open', () => {
    reconnectDelay = 1000;
    console.log('✔ Connected to server\n');
    render();
  });

  ws.on('message', (data) => {
    try {
      const msg = JSON.parse(data.toString());
      log('Raw message:', msg);
      const payload = msg.data ?? msg;
      handlePayload(payload);
    } catch (err) {
      log('Invalid JSON:', data.toString());
    }
  });

  ws.on('close', (code, reason) => {
    console.log(`Socket closed (code=${code})`);
    render();
    if (!manualDisconnect) scheduleReconnect();
  });

  ws.on('error', (err) => {
    console.log('Socket error:', err.message || err);
  });
}

function disconnect(manual = true) {
  manualDisconnect = manual;
  if (ws) {
    try {
      ws.close();
    } catch (e) { /* ignore */ }
    ws = null;
  }
  clearReconnectTimer();
  console.log('Disconnected (manual disconnect = ' + manual + ')');
  render();
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  const delaySec = Math.round(reconnectDelay / 1000);
  console.log(`Reconnecting in ${delaySec}s...`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    if (!manualDisconnect) {
      console.log('Attempting reconnect...');
      connect();
      reconnectDelay = Math.min(Math.floor(reconnectDelay * 1.5), 30000);
    }
  }, reconnectDelay);
}

function clearReconnectTimer() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function render() {
  printHeader();
  printTable();
  process.stdout.write('\n> '); // prompt
}

function handleCommand(line) {
  const parts = line.trim().split(/\s+/);
  const cmd = parts[0]?.toLowerCase();
  switch (cmd) {
    case 'c':
    case 'connect':
      connect();
      break;

    case 'd':
    case 'disconnect':
      disconnect(true);
      break;

    case 'f':
    case 'filter':
      filterId = parts.slice(1).join(' ').trim();
      if (filterId === '') filterId = '';
      console.log('Filter set to:', filterId || '(none)');
      render();
      break;

    case 'l':
    case 'log':
      showLog = !showLog;
      console.log('Log is now', showLog ? 'ON' : 'OFF');
      render();
      break;

    case 'u':
    case 'url':
      const newUrl = parts.slice(1).join(' ').trim();
      if (newUrl) {
        wsUrl = newUrl;
        console.log('WS URL changed to', wsUrl);
      } else {
        console.log('Usage: u <ws_url>');
      }
      render();
      break;

    case 'q':
    case 'quit':
      console.log('Quitting...');
      disconnect(true);
      rl.close();
      process.exit(0);
      break;

    case '':
      // ignore empty
      break;

    default:
      console.log('Unknown command:', cmd);
      console.log('Commands: c connect | d disconnect | f filter <id|empty> | l log | u url <ws> | q quit');
      break;
  }
}

rl.on('line', (line) => {
  handleCommand(line);
});

rl.on('SIGINT', () => {
  console.log('\nReceived SIGINT. Exiting...');
  disconnect(true);
  process.exit(0);
});

// initial render and help
render();
console.log('Type "c" to connect, "q" to quit. (press Enter after a command)');
