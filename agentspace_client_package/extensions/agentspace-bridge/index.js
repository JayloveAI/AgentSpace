const { spawn } = require('child_process');
const os = require('os');
const fs = require('fs');
const path = require('path');

const isWindows = os.platform() === 'win32';
const AGENTSPACE_PID_FILE = path.join(os.homedir(), '.agentspace', '.agentspace.pid');

function isAgentSpaceRunning() {
  try {
    if (fs.existsSync(AGENTSPACE_PID_FILE)) {
      const pid = parseInt(fs.readFileSync(AGENTSPACE_PID_FILE, 'utf8').trim(), 10);
      try { process.kill(pid, 0); return true; } catch (e) {}
    }
  } catch (e) {}
  return false;
}

function startAgentSpace(log) {
  if (isAgentSpaceRunning()) {
    log?.info('[AgentSpace] AgentSpace 已在运行中');
    return;
  }
  const agentspaceCmd = isWindows ? 'agentspace.exe' : 'agentspace';
  log?.info('[AgentSpace] 正在启动 AgentSpace...');
  const child = spawn(agentspaceCmd, ['start'], { detached: !isWindows, stdio: 'ignore', shell: isWindows });
  if (isWindows) child.unref();
}

function stopAgentSpace(log) {
  if (!isAgentSpaceRunning()) {
    log?.info('[AgentSpace] AgentSpace 未运行');
    return;
  }
  log?.info('[AgentSpace] 正在停止 AgentSpace...');
  try {
    const pid = parseInt(fs.readFileSync(AGENTSPACE_PID_FILE, 'utf8').trim(), 10);
    try { process.kill(pid, 'SIGTERM'); } catch (e) {}
  } catch (e) {}
  if (isWindows) {
    spawn('taskkill', ['/F', '/IM', 'agentspace.exe'], { stdio: 'ignore' });
  } else {
    spawn('pkill', ['-f', 'agentspace'], { stdio: 'ignore' });
  }
}

const handler = async ({ event, log }) => {
  if (event === 'gateway:startup' || event === 'start') {
    log?.info('[AgentSpace] 检测到 gateway:startup 事件');
    startAgentSpace(log);
  } else if (event === 'gateway:shutdown' || event === 'stop') {
    log?.info('[AgentSpace] 检测到 gateway:shutdown 事件');
    stopAgentSpace(log);
  }
};

module.exports = handler;
module.exports.startAgentSpace = startAgentSpace;
module.exports.stopAgentSpace = stopAgentSpace;
