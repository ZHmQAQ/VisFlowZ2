import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getEngineStatus } from '../api'

export const useEngineStore = defineStore('engine', () => {
  const status = ref({
    running: false,
    scan_count: 0,
    last_scan_ms: 0,
    target_cycle_ms: 20,
    plc_connections: {},
    io_mappings: 0,
    program_blocks: 0,
  })

  const running = computed(() => status.value.running)
  const scanCount = computed(() => status.value.scan_count)
  const lastScanMs = computed(() => status.value.last_scan_ms)
  const plcConnectionCount = computed(() => Object.keys(status.value.plc_connections || {}).length)
  const plcConnectedCount = computed(
    () => Object.values(status.value.plc_connections || {}).filter(Boolean).length
  )

  let _pollTimer = null
  let _inFlight = false

  async function refresh() {
    if (document.hidden || _inFlight) return
    _inFlight = true
    try {
      const data = await getEngineStatus()
      Object.assign(status.value, data)
    } catch { /* ignore */ } finally {
      _inFlight = false
    }
  }

  function startPolling(interval = 1000) {
    stopPolling()
    refresh()
    _pollTimer = setInterval(refresh, interval)
  }

  function stopPolling() {
    if (_pollTimer) {
      clearInterval(_pollTimer)
      _pollTimer = null
    }
  }

  return {
    status,
    running,
    scanCount,
    lastScanMs,
    plcConnectionCount,
    plcConnectedCount,
    refresh,
    startPolling,
    stopPolling,
  }
})
