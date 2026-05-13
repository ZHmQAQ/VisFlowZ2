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
export const uploadModel = (file) =>
  request.post('/model/upload', file, {
    params: { filename: file.name },
    headers: { 'Content-Type': 'application/octet-stream' },
  })

// ============ Preset ============
export const loadPreset = (data) => request.post('/plc/preset/load', data)
export const savePreset = () => request.get('/plc/preset/save')
export const listPresets = () => request.get('/plc/presets')
export const getPreset = (name) => request.get(`/plc/presets/${name}`)
export const loadNamedPreset = (name) => request.post(`/plc/presets/${name}/load`)

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
export const getRecordStatistics = (params) => request.get('/system/records/statistics', { params })
export const deleteRecord = (id) => request.delete(`/system/records/${id}`)

// ============ Config / GPU ============
export const exportConfig = () => request.get('/config/export')
export const importConfig = (data) => request.post('/config/import', data)
export const getVisflowzSelfCheck = () => request.get('/config/visflowz-self-check')
export const getGpuInfo = () => request.get('/gpu')

// ============ Devices ============
export const listDevices = () => request.get('/devices')
export const addDevice = (data) => request.post('/devices', data)
export const getDevice = (id) => request.get(`/devices/${id}`)
export const updateDevice = (id, data) => request.put(`/devices/${id}`, data)
export const deleteDevice = (id) => request.delete(`/devices/${id}`)
export const connectDevice = (id) => request.post(`/devices/${id}/connect`)
export const disconnectDevice = (id) => request.post(`/devices/${id}/disconnect`)
export const sendDevice = (id, data) => request.post(`/devices/${id}/send`, data)

// ============ Event Actions ============
export const getEventActionMeta = () => request.get('/event-actions/meta')
export const listEventActions = () => request.get('/event-actions')
export const addEventAction = (data) => request.post('/event-actions', data)
export const updateEventAction = (id, data) => request.put(`/event-actions/${id}`, data)
export const deleteEventAction = (id) => request.delete(`/event-actions/${id}`)
export const batchSetEventActions = (data) => request.post('/event-actions/batch', data)
export const listEventActionTemplates = () => request.get('/event-actions/templates')
export const generateEventActions = (data) => request.post('/event-actions/generate', data)
export const testEventAction = (data) => request.post('/event-actions/test', data)

// ============ Rules ============
export const listRules = () => request.get('/rules')
export const addRule = (data) => request.post('/rules', data)
export const getRule = (id) => request.get(`/rules/${id}`)
export const updateRule = (id, data) => request.put(`/rules/${id}`, data)
export const deleteRule = (id) => request.delete(`/rules/${id}`)
export const enableRule = (id) => request.post(`/rules/${id}/enable`)
export const disableRule = (id) => request.post(`/rules/${id}/disable`)
export const evaluateRules = (data) => request.post('/rules/evaluate', data)
