import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import PrimeVue from 'primevue/config'
import TooltipDirective from 'primevue/tooltip'
import Aura from '@primevue/themes/aura'
import { definePreset } from '@primevue/themes'

const Theme = definePreset(Aura, {
  semantic: {
    colorScheme: {
      dark: {
        content: {
          background: '{stone.800}', // stone-800 (#292524) — lifts cards off the stone-900 page
        },
      },
    },
  },
})
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js'
import App from './App.vue'
import './style.css'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Filler, Tooltip, Legend)

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('./views/OverviewView.vue') },
    { path: '/dashboard', component: () => import('./views/DashboardView.vue') },
    { path: '/timeline', component: () => import('./views/TimelineView.vue') },
    { path: '/detailed-report', component: () => import('./views/DetailedReportView.vue') },
  ],
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: Theme,
    options: {
      darkModeSelector: '.dark',
      cssLayer: {
        name: 'primevue',
        order: 'tailwind-base, primevue, tailwind-utilities',
      },
    },
  },
})

app.directive('tooltip', TooltipDirective)

app.mount('#app')
