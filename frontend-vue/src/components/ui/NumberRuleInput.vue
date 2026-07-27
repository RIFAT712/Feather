<script setup>
import { CdxTextInput } from '@wikimedia/codex';

/**
 * NumberRuleInput — A numeric rule input with label, preset-chip shortcuts, and hint text.
 *
 * Props:
 *   modelValue (Number) — the v-model binding
 *   label (String)      — field label (may include emoji prefix)
 *   placeholder (String)
 *   hint (String)       — optional hint text shown below
 *   presets (Array)     — array of { label, value } objects for quick-select chips
 *   span2 (Boolean)     — whether to apply span-2 class (full-width in 2-col grid)
 */
defineProps({
  modelValue:  { type: Number, default: 0 },
  label:       { type: String, required: true },
  placeholder: { type: String, default: '0 = No limit' },
  hint:        { type: String, default: '' },
  presets:     { type: Array, default: () => [] }, // [{ label: 'No Limit', value: 0 }, ...]
  span2:       { type: Boolean, default: false },
});
defineEmits(['update:modelValue']);
</script>

<template>
  <div class="rule-input-card" :class="{ 'span-2': span2 }">
    <label class="field-label">{{ label }}</label>
    <div class="flex-input-row">
      <CdxTextInput
        :model-value="modelValue"
        type="number"
        :placeholder="placeholder"
        @update:model-value="$emit('update:modelValue', Number($event))"
      />
      <div v-if="presets.length" class="preset-chips">
        <button
          v-for="p in presets"
          :key="p.value"
          class="preset-chip"
          :class="{ active: modelValue === p.value }"
          type="button"
          @click="$emit('update:modelValue', p.value)"
        >
          {{ p.label }}
        </button>
      </div>
    </div>
    <p v-if="hint" class="field-hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.rule-input-card {
  background: #16192c;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px;
  padding: 14px 18px;
  transition: border-color 0.2s;
}
.rule-input-card:hover { border-color: rgba(255,255,255,0.1); }
.rule-input-card.span-2 { grid-column: span 2; }

.field-label {
  display: block;
  font-size: 0.85rem;
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: 10px;
  letter-spacing: 0.01em;
}
.flex-input-row { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; }

.preset-chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.preset-chip {
  padding: 4px 12px;
  border-radius: 20px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.04);
  color: #94a3b8;
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.preset-chip:hover { background: rgba(255,255,255,0.12); color: #fff; border-color: rgba(255,255,255,0.2); }
.preset-chip.active {
  background: #ffffff;
  color: #fff;
  border-color: #ffffff;
  box-shadow: 0 0 8px rgba(255,255,255,0.1);
}

.field-hint {
  font-size: 0.78rem;
  color: #64748b;
  margin-top: 8px;
  line-height: 1.4;
}
</style>
