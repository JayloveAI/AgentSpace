const { spawn } = require('child_process');
const os = require('os');
const fs = require('fs');
const path = require('path');

const isWindows = os.platform() === 'win32';
const CLAWHUB_PID_FILE = path.join(os.homedir(), '.clawhub', '.clawhub.pid');

function isClawHubRunning() {
  try {
    if (fs.existsSync(CLAWHUB_PID_FILE)) {
      const pid = parseInt(fs.readFileSync(CLAWHUB_PID_FILE, 'utf8').trim(), 10);
      try { process.kill(pid, 0); return true; } catch (e) {}
    }
  } catch (e) {}
  return false;
}

function startClawHub(log) {
  if (isClawHubRunning()) {
    log?.info('[ClawHub] ClawHub 已在运行中');
    return;
  }
  const clawhubCmd = isWindows ? 'clawhub.exe' : 'clawhub';
  log?.info('[ClawHub] 正在启动 ClawHub...');
  const child = spawn(clawhubCmd, ['start'], { detached: !isWindows, stdio: 'ignore', shell: isWindows });
  if (isWindows) child.unref();
}

function stopClawHub(log) {
  if (!isClawHubRunning()) {
    log?.info('[ClawHub] ClawHub 未运行');
    return;
  }
  log?.info('[ClawHub] 正在停止 ClawHub...');
  try {
    const pid = parseInt(fs.readFileSync(CLAWHUB_PID_FILE, 'utf8').trim(), 10);
    try { process.kill(pid, 'SIGTERM'); } catch (e) {}
  } catch (e) {}
  if (isWindows) {
    spawn('taskkill', ['/F', '/IM', 'clawhub.exe'], { stdio: 'ignore' });
  } else {
    spawn('pkill', ['-f', 'clawhub'], { stdio: 'ignore' });
  }
}

const handler = async ({ event, log }) => {
  if (event === 'gateway:startup' || event === 'start') {
    log?.info('[ClawHub] 检测到 gateway:startup 事件');
    startClawHub(log);
  } else if (event === 'gateway:shutdown' || event === 'stop') {
    log?.info('[ClawHub] 检测到 gateway:shutdown 事件');
    stopClawHub(log);
  }
};

module.exports = handler;
module.exports.startClawHub = startClawHub;
module.exports.stopClawHub = stopClawHub;
