// LifeBoard — widget registry. Checks for a custom renderer first,
// falls back to the generic card renderer. Per docs/ARCHITECTURE.md's
// frontend widget contract.

const WidgetRegistry = {
  _custom: {
    clock: ClockWidget,
    nutrition: NutritionWidget,
  },

  getRenderer(moduleId) {
    return this._custom[moduleId] || GenericWidget;
  },
};
