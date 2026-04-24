import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '../views/Layout.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '仪表盘', icon: 'Odometer' } },
      { path: 'plc', name: 'PLC', component: () => import('../views/PLCConfig.vue'), meta: { title: 'PLC 连接', icon: 'Connection' } },
      { path: 'mappings', name: 'Mappings', component: () => import('../views/IOMappings.vue'), meta: { title: 'I/O 映射', icon: 'Switch' } },
      { path: 'detection', name: 'Detection', component: () => import('../views/Detection.vue'), meta: { title: '检测通道', icon: 'Camera' } },
      { path: 'topology', name: 'Topology', component: () => import('../views/Topology.vue'), meta: { title: '系统拓扑', icon: 'Share' } },
      { path: 'monitor', name: 'Monitor', component: () => import('../views/DeviceMonitor.vue'), meta: { title: '软元件监控', icon: 'Monitor' } },
      { path: 'cameras', name: 'Cameras', component: () => import('../views/Cameras.vue'), meta: { title: '相机管理', icon: 'VideoCamera' } },
      { path: 'models', name: 'Models', component: () => import('../views/Models.vue'), meta: { title: '模型管理', icon: 'Cpu' } },
      { path: 'records', name: 'Records', component: () => import('../views/Records.vue'), meta: { title: '检测记录', icon: 'Document' } },
      { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { title: '系统设置', icon: 'Setting' } },
    ],
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
