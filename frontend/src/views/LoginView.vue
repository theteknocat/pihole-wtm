<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputGroup from 'primevue/inputgroup'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useAuth } from '@/composables/useAuth'

const router = useRouter()
const { piholeUrl, login } = useAuth()

// Form state
const urlInput = ref('')
const passwordInput = ref('')
const error = ref<string | null>(null)
const loading = ref(false)

// Pi-hole reachability check
const urlChecking = ref(false)
const urlReachable = ref<boolean | null>(null)
const piholeVersion = ref<string | null>(null)

// If the URL is set via env or saved config, the user shouldn't need to enter it
const needsUrl = ref(false)

onMounted(async () => {
  // If there's already a configured URL, check if it's reachable
  if (piholeUrl.value) {
    urlInput.value = piholeUrl.value
    await checkUrl(piholeUrl.value)
  } else {
    needsUrl.value = true
  }
})

async function checkUrl(url: string) {
  if (!url.trim()) return
  urlChecking.value = true
  urlReachable.value = null
  piholeVersion.value = null
  try {
    const res = await fetch(`/api/auth/check-url?url=${encodeURIComponent(url.trim())}`)
    const data = await res.json()
    urlReachable.value = data.reachable
    piholeVersion.value = data.version ?? null
    error.value = null
  } catch {
    urlReachable.value = false
  } finally {
    urlChecking.value = false
  }
}

async function handleLogin() {
  error.value = null
  if (!passwordInput.value.trim()) {
    error.value = 'Password is required'
    return
  }
  const url = needsUrl.value ? urlInput.value.trim() : undefined
  if (needsUrl.value && !url) {
    error.value = 'Pi-hole URL is required'
    return
  }

  loading.value = true
  const result = await login(passwordInput.value, url)
  loading.value = false

  if (result.ok) {
    router.push('/dashboard')
  } else {
    error.value = result.error ?? 'Login failed'
  }
}
</script>

<template>
  <div class="flex flex-col items-center justify-center h-full gap-6 p-6">
    <div class="text-center">
      <h1 class="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100">pihole-wtm</h1>
      <p class="text-gray-500 dark:text-gray-400 text-lg mt-2">Pi-hole enriched with tracker intelligence</p>
    </div>

    <Card class="w-96" :pt="{ root: { class: 'border border-gray-200 dark:border-transparent' } }">
      <template #content>
        <form class="space-y-4" @submit.prevent="handleLogin">
          <!-- Pi-hole URL field — shown when no URL is configured -->
          <div v-if="needsUrl" class="space-y-1">
            <div class="flex items-center justify-between">
              <label for="pihole-url" class="text-sm font-medium text-gray-700 dark:text-gray-300">Pi-hole URL</label>
              <span v-if="urlReachable === true" class="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                <i class="pi pi-check-circle" />
                Reachable<span v-if="piholeVersion"> &mdash; v{{ piholeVersion }}</span>
              </span>
              <span v-else-if="urlReachable === false" class="text-xs text-red-400 flex items-center gap-1">
                <i class="pi pi-times-circle" />
                Not reachable
              </span>
              <span v-else-if="urlChecking" class="text-xs text-gray-400 flex items-center gap-1">
                <i class="pi pi-spin pi-spinner" />
                Checking...
              </span>
            </div>
            <InputGroup>
              <InputText
                id="pihole-url"
                v-model="urlInput"
                placeholder="http://192.168.1.2"
                class="flex-1"
                @blur="checkUrl(urlInput)"
              />
              <Button
                type="button"
                icon="pi pi-link"
                severity="secondary"
                outlined
                :loading="urlChecking"
                @click="checkUrl(urlInput)"
                v-tooltip.top="'Check reachability'"
              />
            </InputGroup>
          </div>

          <!-- Show configured URL as read-only info when set via env or saved -->
          <div v-else class="space-y-1">
            <div class="flex items-center justify-between">
              <span class="text-sm text-gray-500 dark:text-gray-400">Pi-hole</span>
              <span v-if="urlReachable === true" class="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                <i class="pi pi-check-circle" />
                Reachable<span v-if="piholeVersion"> &mdash; v{{ piholeVersion }}</span>
              </span>
              <span v-else-if="urlReachable === false" class="text-xs text-red-400 flex items-center gap-1">
                <i class="pi pi-times-circle" />
                Not reachable
              </span>
              <span v-else-if="urlChecking" class="text-xs text-gray-400 flex items-center gap-1">
                <i class="pi pi-spin pi-spinner" />
                Checking...
              </span>
            </div>
            <span class="text-sm font-mono text-gray-700 dark:text-gray-300">{{ piholeUrl }}</span>
          </div>

          <!-- Hidden username for password managers -->
          <input
            type="text"
            name="username"
            autocomplete="username"
            value="pihole-wtm"
            readonly
            tabindex="-1"
            aria-hidden="true"
            class="absolute w-0 h-0 overflow-hidden opacity-0"
          />

          <!-- Password -->
          <div class="space-y-1">
            <label for="pihole-password" class="text-sm font-medium text-gray-700 dark:text-gray-300">Pi-hole Password</label>
            <Password
              id="pihole-password"
              v-model="passwordInput"
              :feedback="false"
              toggleMask
              fluid
              placeholder="Enter your Pi-hole password"
              :disabled="urlReachable !== true"
              :pt="{ pcInput: { root: { class: 'w-full', autocomplete: 'current-password' } } }"
              @keydown.enter="handleLogin"
            />
          </div>

          <Message v-if="error" severity="error" :closable="false" class="text-sm">
            {{ error }}
          </Message>

          <Button
            type="submit"
            label="Sign in"
            icon="pi pi-sign-in"
            class="w-full"
            :loading="loading"
            :disabled="loading || urlReachable !== true"
          />
        </form>
      </template>
    </Card>
  </div>
</template>
