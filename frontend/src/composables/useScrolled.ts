import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Tracks whether the nearest scrollable ancestor (`<main>`) has scrolled
 * past a threshold. Uses hysteresis and a delay on deactivation to prevent
 * jitter when the header's height change shifts the scroll position.
 */
export function useScrolled(activateAt = 48, deactivateAt = 8, deactivateDelay = 150) {
  const scrolled = ref(false)
  let deactivateTimer: ReturnType<typeof setTimeout> | null = null

  function onScroll(e: Event) {
    const top = (e.target as HTMLElement).scrollTop

    if (!scrolled.value && top > activateAt) {
      if (deactivateTimer) { clearTimeout(deactivateTimer); deactivateTimer = null }
      scrolled.value = true
    } else if (scrolled.value && top < deactivateAt) {
      // Delay before removing scrolled — gives the layout time to settle
      if (!deactivateTimer) {
        deactivateTimer = setTimeout(() => {
          deactivateTimer = null
          scrolled.value = false
        }, deactivateDelay)
      }
    } else if (scrolled.value && top >= deactivateAt) {
      // Scrolled back down before delay fired — cancel deactivation
      if (deactivateTimer) { clearTimeout(deactivateTimer); deactivateTimer = null }
    }
  }

  let el: HTMLElement | null = null

  onMounted(() => {
    el = document.querySelector('main')
    if (el) el.addEventListener('scroll', onScroll, { passive: true })
  })

  onUnmounted(() => {
    if (el) el.removeEventListener('scroll', onScroll)
    if (deactivateTimer) clearTimeout(deactivateTimer)
  })

  return scrolled
}
