const levels = { info: '›', warn: '⚠', error: '✗' }

function log(level, ...args) {
  console.log(`[${new Date().toISOString()}] ${levels[level] ?? '›'}`, ...args)
}

export const logger = {
  info:  (...a) => log('info',  ...a),
  warn:  (...a) => log('warn',  ...a),
  error: (...a) => log('error', ...a),
}
