<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';

// Lifted out of UserProfile, which had the only copy, when the contest page
// wanted the same thing. Owns its own listener and its own styles so a view
// gets the whole behaviour from one tag.
const props = defineProps({
  // How far down the page the button appears. A little under one screen, so it
  // never covers content the reader has not scrolled past yet.
  after: { type: Number, default: 420 },
});

const show = ref(false);
const update = () => { show.value = window.scrollY > props.after; };
const toTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

onMounted(() => {
  update();
  window.addEventListener('scroll', update, { passive: true });
});
onBeforeUnmount(() => window.removeEventListener('scroll', update));
</script>

<template>
  <button
    v-if="show"
    class="scroll-top-button"
    type="button"
    aria-label="Back to top"
    title="Back to top"
    @click="toTop"
  >
    <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m10 3.2 6.2 6.2-1.4 1.4-3.8-3.8V17H9V7l-3.8 3.8-1.4-1.4z" /></svg>
  </button>
</template>

<style>
.scroll-top-button { position: fixed; right: 24px; bottom: 24px; z-index: 80; display: inline-grid; width: 48px; height: 48px; place-items: center; padding: 0; border: 1px solid #b8cedd; border-radius: 50%; background: rgba(255,255,255,.96); box-shadow: 0 8px 22px rgba(32,54,77,.16); color: #355b80; cursor: pointer; transition: background .15s ease, border-color .15s ease, transform .15s ease; }
.scroll-top-button:hover { background: #eef5f9; border-color: #8eacc3; transform: translateY(-2px); }
.scroll-top-button:focus-visible { outline: 3px solid rgba(53,91,128,.25); outline-offset: 3px; }
.scroll-top-button svg { width: 21px; height: 21px; fill: currentColor; }
@media (max-width: 640px) { .scroll-top-button { right: 14px; bottom: 16px; } }
</style>
