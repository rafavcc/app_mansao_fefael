// A real <select> inside a Quasar field: iOS shows its wheel picker, Android/desktop their native list.
export default {
  props: ["options", "modelValue"],
  emits: ["update:modelValue"],
  template: `
    <q-field :model-value="modelValue ? String(modelValue.label) : ''" stack-label>
      <template v-slot:control>
        <select class="q-field__native casa-native-select" :value="modelValue ? modelValue.value : ''" @change="onChange">
          <option value="" disabled hidden></option>
          <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </template>
      <template v-slot:append>
        <q-icon name="arrow_drop_down" />
      </template>
    </q-field>
  `,
  methods: {
    onChange(event) {
      const selected = this.options.find((o) => String(o.value) === event.target.value);
      this.$emit("update:modelValue", selected ? { value: selected.value, label: selected.label } : null);
    },
  },
};
