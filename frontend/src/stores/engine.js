import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getEngineStatus } from '../api'

export const useEngineStore = defineStore('engine', () => {
  const status = ref({
    running: false,
    scan_count: 0,
    last_scan_ms: 0,
    target_cycle_ms: 20,
    plc_clients: 0,
    io_mappings: 0,
    program_blocks: 0,
  })

  const running = computed(() => status.value.running)
  const scanCount = computed(() => status.value.scan_count)
  const lastScanMs = computed(() => status.value.last_scan_ms)

  let _pollTimer = null

  async function refresh() {
    try {
      const data = await getEngineStatus()
      Object.assign(status.value, data)
    } catch { /* ignore */ }
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

  return { status, running, scanCount, lastScanMs, refresh, startPolling, stopPolling }
})
