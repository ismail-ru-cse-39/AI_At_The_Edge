// Plain JavaScript. Text is updated without rebuilding the page or moving keyboard focus.
const pauseButton = document.querySelector('#pause-updates');
const connectionNote = document.querySelector('#connection-note');
let paused = false;
pauseButton.hidden = false;
pauseButton.addEventListener('click', () => {
  paused = !paused;
  pauseButton.textContent = paused ? 'Resume dashboard updates' : 'Pause dashboard updates';
  connectionNote.textContent = paused
    ? 'Dashboard updates paused. Displayed readings are frozen; sensor collection continues.'
    : 'Dashboard updates resumed.';
});

async function refresh() {
  if (!paused) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await fetch('/api/status', {cache: 'no-store', signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const values = await response.json();
      if (!paused) {
        document.querySelectorAll('[data-field]').forEach(element => {
          const value = String(values[element.dataset.field] ?? 'Unavailable');
          if (element.textContent !== value) element.textContent = value;
        });
        connectionNote.textContent = 'Dashboard connected to the local Pi application.';
      }
    } catch (error) {
      if (!paused) connectionNote.textContent =
        'Dashboard connection lost. Readings shown are last known values, not current measurements.';
    } finally {
      clearTimeout(timeout);
    }
  }
  // Schedule AFTER completion: slow requests cannot accumulate into overlapping polls.
  setTimeout(refresh, 5000);
}
refresh();
