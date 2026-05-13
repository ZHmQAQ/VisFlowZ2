import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '../views/Layout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '\u4eea\u8868\u76d8', icon: 'Odometer' } },
      { path: 'plc', name: 'PLC', component: () => import('../views/PLCConfig.vue'), meta: { title: 'PLC \u8fde\u63a5', icon: 'Connection' } },
      { path: 'mappings', name: 'Mappings', component: () => import('../views/IOMappings.vue'), meta: { title: 'I/O \u6620\u5c04', icon: 'Switch' } },
      { path: 'detection', name: 'Detection', component: () => import('../views/Detection.vue'), meta: { title: '\u68c0\u6d4b\u901a\u9053', icon: 'Camera' } },
      { path: 'topology', name: 'Topology', component: () => import('../views/Topology.vue'), meta: { title: '\u7cfb\u7edf\u62d3\u6251', icon: 'Share' } },
      { path: 'ladder', name: 'Ladder', component: () => import('../views/Ladder.vue'), meta: { title: '\u68af\u5f62\u56fe', icon: 'Connection' } },
      { path: 'monitor', name: 'Monitor', component: () => import('../views/DeviceMonitor.vue'), meta: { title: '\u8f6f\u5143\u4ef6\u76d1\u63a7', icon: 'Monitor' } },
      { path: 'cameras', name: 'Cameras', component: () => import('../views/Cameras.vue'), meta: { title: '\u76f8\u673a\u7ba1\u7406', icon: 'VideoCamera' } },
      { path: 'devices', name: 'Devices', component: () => import('../views/Devices.vue'), meta: { title: '\u5916\u90e8\u8bbe\u5907', icon: 'Cpu' } },
      { path: 'event-actions', name: 'EventActions', component: () => import('../views/EventActions.vue'), meta: { title: '\u4e8b\u4ef6\u52a8\u4f5c', icon: 'Operation' } },
      { path: 'rules', name: 'Rules', component: () => import('../views/Rules.vue'), meta: { title: '\u89c4\u5219\u5f15\u64ce', icon: 'SetUp' } },
      { path: 'models', name: 'Models', component: () => import('../views/Models.vue'), meta: { title: '\u6a21\u578b\u7ba1\u7406', icon: 'Cpu' } },
      { path: 'records', name: 'Records', component: () => import('../views/Records.vue'), meta: { title: '\u68c0\u6d4b\u8bb0\u5f55', icon: 'Document' } },
      { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { title: '\u7cfb\u7edf\u8bbe\u7f6e', icon: 'Setting' } },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
