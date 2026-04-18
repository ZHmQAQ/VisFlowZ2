import request from './request'

// ============ PLC 连接 ============
export const addPLC = (data) => request.post('/plc/connections', data)
export const listPLC = () => request.get('/plc/connections')
export const removePLC = (name) => request.delete(`/plc/connections/${name}`)

// ============ I/O 映射 ============
export const addMapping = (data) => request.post('/plc/mappings', data)
export const addMappingsBatch = (data) => request.post('/plc/mappings/batch', data)
export const listMappings = () => request.get('/plc/mappings')
export const clearMappings = () => request.delete('/plc/mappings')

// ============ 软元件读写 ============
export const readDevice = (address) => request.get(`/plc/device/${address}`)
export const writeDevice = (data) => request.post('/plc/device/write', data)
export const bulkReadDevice = (addresses) => request.post('/plc/device/bulk-read', { addresses })
export const dumpDevice = (prefix, start = 0, count = 32) =>
  request.get(`/plc/device/dump/${prefix}`, { params: { start, count } })

// ============ 引擎控制 ============
export const getEngineStatus = () => request.get('/plc/engine/status')
export const startEngine = () => request.post('/plc/engine/start')
export const stopEngine = () => request.post('/plc/engine/stop')

// ============ 检测通道 ============
export const addChannel = (data) => request.post('/detection/channels', data)
export const listChannels = () => request.get('/detection/channels')

// ============ 预设 ============
export const loadPreset = (data) => request.post('/plc/preset/load', data)

// ============ 健康检查 ============
export const getHealth = () => request.get('/health', { baseURL: '' })
