import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../components/HomePage.vue'
import RecordPage from '../components/RecordPage.vue'
import SettingsPage from '../components/SettingsPage.vue'
import SpeakerRegistration from '../components/SpeakerRegistration.vue'
import MeetingDetail from '../components/MeetingDetail.vue'
import HotwordsPage from '../components/HotwordsPage.vue'
import SerialPortSettings from '../components/SerialPortSettings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      redirect: to => {
        const redirect = Array.isArray(to.query.redirect)
          ? to.query.redirect[0]
          : to.query.redirect

        if (typeof redirect === 'string' && redirect.startsWith('/')) {
          return {
            path: redirect === '/index' ? '/' : redirect,
            query: {}
          }
        }

        return { path: '/', query: {} }
      }
    },
    {
      path: '/index',
      redirect: '/'
    },
    {
      path: '/',
      name: 'home',
      component: HomePage
    },
    {
      path: '/record',
      name: 'record',
      component: RecordPage
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsPage
    },
    {
      path: '/speaker-registration',
      name: 'speaker-registration',
      component: SpeakerRegistration
    },
    {
      path: '/meeting-detail',
      name: 'meeting-detail',
      component: MeetingDetail
    },
    {
      path: '/hotwords',
      name: 'hotwords',
      component: HotwordsPage
    },
    {
      path: '/serial-port-settings',
      name: 'serial-port-settings',
      component: SerialPortSettings
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/'
    }
  ]
})

export default router
