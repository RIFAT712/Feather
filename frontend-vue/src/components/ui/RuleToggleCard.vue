<script setup>
/**
 * RuleToggleCard — A checkbox rule card with a title, description, and optional expanded slot.
 *
 * Props:
 *   modelValue (Boolean) — the checkbox v-model binding
 *   title (String)       — the bold rule title (may include emoji prefix)
 *   description (String) — subtle helper text below the title
 *
 * Slots:
 *   default — optional expanded content shown below the checkbox row (e.g. extra fields)
 */
defineProps({
  modelValue: { type: Boolean, default: false },
  title:       { type: String, required: true },
  description: { type: String, default: '' },
});
defineEmits(['update:modelValue']);
</script>

<template>
  <div class="rule-card-toggle">
    <label class="rule-toggle-row">
      <input
        type="checkbox"
        class="rule-checkbox"
        :checked="modelValue"
        @change="$emit('update:modelValue', $event.target.checked)"
      />
      <span class="rule-toggle-content">
        <strong class="rule-title">{{ title }}</strong>
        <span v-if="description" class="toggle-desc">{{ description }}</span>
      </span>
    </label>
    <div v-if="$slots.default" class="rule-expanded">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.rule-card-toggle {
  background: #1a1a1a;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px;
  padding: 14px 18px;
  transition: border-color 0.2s;
}
.rule-card-toggle:hover {
  border-color: rgba(255,255,255,0.1);
}
.rule-toggle-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  width: 100%;
}
.rule-checkbox {
  margin-top: 3px;
  accent-color: #ffffff;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  cursor: pointer;
}
.rule-toggle-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.rule-title {
  color: #f1f5f9;
  font-size: 0.9rem;
  font-weight: 600;
  line-height: 1.4;
}
.toggle-desc {
  font-size: 0.82rem;
  color: #94a3b8;
  font-weight: normal;
  line-height: 1.4;
}
.rule-expanded {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.06);
}
</style>
