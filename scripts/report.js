'use strict';
// All charts have server-rendered text and tables; interaction is progressive enhancement.
document.querySelectorAll('[data-filter-group]').forEach(group => {
  group.addEventListener('click', event => {
    const button = event.target.closest('button[data-panel]');
    if (!button) return;
    group.querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.querySelectorAll(`[data-group="${group.dataset.filterGroup}"]`).forEach(panel => {
      panel.hidden = panel.id !== button.dataset.panel;
    });
  });
});
