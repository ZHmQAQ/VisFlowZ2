import request from './request'

// ============ PLC ============
export const addPLC = (data) => request.post('/plc/connections', data)
export const listPLC = () => request.get('/plc/connections')
export const removePLC = (name) => request.delete(`/plc/connections/${name}`)
export const connectPLC = (name) => request.post(`/plc/connections/${name}/connect`)
export const disconnectPLC = (name) => request.post(`/plc/connections/${name}/disconnect`)
export const updatePLC = (name, data) => request.put(`/plc/connections/${name}`, data)

// ============ I/O Mappings ============
export const addMapping = (data) => request.post('/plc/mappings', data)
export const addMappingsBatch = (data) => request.post('/plc/mappings/batch', data)
export const listMappings = () => request.get('/plc/mappings')
export const clearMappings = () => request.delete('/plc/mappings')
export const deleteMapping = (id) => request.delete(`/plc/mappings/${id}`)
export const updateMapping = (id, data) => request.put(`/plc/mappings/${id}`, data)
export const toggleMapping = (id) => request.patch(`/plc/mappings/${id}/toggle`)

// ============ Soft Device ============
export const readDevice = (address) => request.get(`/plc/device/${address}`)
export const writeDevice = (data) => request.post('/plc/device/write', data)
export const bulkReadDevice = (addresses) => request.post('/plc/device/bulk-read', { addresses })
export const dumpDevice = (prefix, start = 0, count = 32) =>
  request.get(`/plc/device/dump/${prefix}`, { params: { start, count } })

// ============ Engine ============
export const getEngineStatus = () => request.get('/plc/engine/status')
export const startEngine = () => request.post('/plc/engine/start')
export const stopEngine = () => request.post('/plc/engine/stop')

// ============ Detection Channels ============
export const addChannel = (data) => request.post('/detection/channels', data)
export const listChannels = () => request.get('/detection/channels')
export const updateChannel = (name, data) => request.put(`/detection/channels/${name}`, data)
export const deleteChannel = (name) => request.delete(`/detection/channels/${name}`)

// ============ Multi-frame Channels ============
export const addMultiframeChannel = (data) => request.post('/detection/multiframe', data)
export const listMultiframeChannels = () => request.get('/detection/multiframe')
export const updateMultiframeChannel = (name, data) => request.put(`/detection/multiframe/${name}`, data)
export const deleteMultiframeChannel = (name) => request.delete(`/detection/multiframe/${name}`)

// ============ Camera ============
export const listCameraTypes = () => request.get('/camera/types')
export const addCamera = (data) => request.post('/camera/add', data)
export const removeCamera = (id) => request.delete(`/camera/${id}`)
export const listCameras = () => request.get('/camera/list')
export const getCameraInfo = (id) => request.get(`/camera/${id}/info`)
export const openCamera = (id) => request.post(`/camera/${id}/open`)
export const closeCamera = (id) => request.post(`/camera/${id}/close`)
export const captureFrame = (id) => request.post(`/camera/${id}/capture`)
export const getFrameBase64 = (id) => request.get(`/camera/${id}/frame/base64`)
export const getFrameUrl = (id) => `/api/camera/${id}/frame.jpg`
export const updateCameraConfig = (id, data) => request.post(`/camera/${id}/config`, data)

// ============ Model ============
export const listWeights = () => request.get('/model/weights')
export const loadModel = (data) => request.post('/model/load', data)
export const unloadModel = (id) => request.post(`/model/${id}/unload`)
export const listModels = () => request.get('/model/list')
export const getModelInfo = (id) => request.get(`/model/${id}/info`)
export const setStrategy = (data) => request.post('/model/strategy', data)
export const getStrategy = (id) => request.get(`/model/${id}/strategy`)

// ============ Preset ============
export const loadPreset = (data) => request.post('/plc/preset/load', data)
export const savePreset = () => request.get('/plc/preset/save')

// ============ Engine Config ============
export const updateEngineConfig = (data) => request.put('/plc/engine/config', data)

// ============ Health ============
export const getHealth = () => request.get('/health', { baseURL: '' })

// ============ System ============
export const getLogLevel = () => request.get('/system/log-level')
export const setLogLevel = (level) => request.put('/system/log-level', { level })
export const getSystemSettings = () => request.get('/system/settings')
export const updateSystemSettings = (data) => request.put('/system/settings', data)
export const saveNow = () => request.post('/system/save-now')
export const getRecords = (params) => request.get('/system/records', { params })
