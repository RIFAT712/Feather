<script setup>
defineProps({
  label: { type: String, default: 'Loading…' },
  fullscreen: { type: Boolean, default: false }
});
</script>

<template>
  <div class="global-loader" :class="{ 'global-loader--fullscreen': fullscreen }" role="status" aria-live="polite">
    <div class="global-loader__mark" aria-hidden="true"><span></span><span></span><span></span></div>
    <span class="global-loader__label">{{ label }}</span>
  </div>
</template>

<style>
.global-loader { display: flex; box-sizing: border-box; width: 100%; min-height: calc(100dvh - var(--app-header-height, 0px)); flex-direction: column; align-items: center; justify-content: center; gap: 14px; color: #6c899c; font: 600 .84rem/1.4 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.global-loader--fullscreen { min-height: 100vh; background: #f4f8fa; }
.global-loader__mark { display: flex; align-items: flex-end; gap: 4px; height: 24px; }
.global-loader__mark span { display: block; width: 5px; height: 10px; border-radius: 5px; background: #4c87aa; animation: global-loader-pulse 1s ease-in-out infinite; }
.global-loader__mark span:nth-child(2) { height: 17px; animation-delay: .14s; }
.global-loader__mark span:nth-child(3) { animation-delay: .28s; }
@keyframes global-loader-pulse { 0%, 100% { opacity: .35; transform: scaleY(.7); } 50% { opacity: 1; transform: scaleY(1); } }
@media (prefers-reduced-motion: reduce) { .global-loader__mark span { animation: none; opacity: .8; } }
</style>
