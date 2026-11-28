/**
 * Meeting timer
 * Segment countdown + total elapsed time.
 * Reads data-duration-minutes, data-segment-started and data-meeting-started
 * (ISO strings) from #meeting-timer.
 *
 * The countdown runs from when the segment started on the server, so it carries
 * on across the page reloads that every action in the runner causes. Pause and
 * Reset belong to this browser tab and are remembered in sessionStorage for the
 * segment they were pressed in.
 */
(function () {
    'use strict';

    const el = document.getElementById('meeting-timer');
    if (!el) return;

    const durationMinutes = parseInt(el.dataset.durationMinutes, 10);
    const meetingStarted = el.dataset.meetingStarted
        ? new Date(el.dataset.meetingStarted)
        : null;

    const segmentStarted = el.dataset.segmentStarted
        ? new Date(el.dataset.segmentStarted).getTime()
        : NaN;

    const segmentMs = durationMinutes * 60 * 1000;
    // Meetings started before segment start times were recorded have none;
    // they count from page load, as every meeting used to.
    let anchorTime = Number.isNaN(segmentStarted) ? Date.now() : segmentStarted;
    let pausedOffset = 0;
    let paused = false;
    let pausedAt = null;
    let alerted = false;

    const storageKey = 'meeting-timer:' + el.dataset.timerKey + ':' + (el.dataset.segmentStarted || '');

    function remember() {
        try {
            sessionStorage.setItem(storageKey, JSON.stringify({ anchorTime, pausedOffset, paused, pausedAt }));
        } catch (e) { /* storage unavailable: the timer still works for this page view */ }
    }

    try {
        const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
        if (saved) {
            ({ anchorTime, pausedOffset, paused, pausedAt } = saved);
        }
    } catch (e) { /* ignore unreadable state */ }

    const segRemEl = document.getElementById('timer-segment-remaining');
    const totalElEl = document.getElementById('timer-total-elapsed');
    const progressEl = document.getElementById('timer-progress');
    const alertEl = document.getElementById('timer-alert');

    document.getElementById('timer-btn-pause')?.addEventListener('click', function () {
        if (paused) {
            pausedOffset += Date.now() - pausedAt;
            paused = false;
            this.textContent = 'Pause';
            this.className = 'btn btn-sm btn-outline-secondary';
        } else {
            pausedAt = Date.now();
            paused = true;
            this.textContent = 'Resume';
            this.className = 'btn btn-sm btn-warning';
        }
        remember();
    });

    document.getElementById('timer-btn-reset')?.addEventListener('click', function () {
        anchorTime = Date.now();
        pausedOffset = 0;
        paused = false;
        alerted = false;
        if (alertEl) alertEl.classList.add('d-none');
        const pauseBtn = document.getElementById('timer-btn-pause');
        if (pauseBtn) { pauseBtn.textContent = 'Pause'; pauseBtn.className = 'btn btn-sm btn-outline-secondary'; }
        remember();
    });

    if (paused) {
        const pauseBtn = document.getElementById('timer-btn-pause');
        if (pauseBtn) { pauseBtn.textContent = 'Resume'; pauseBtn.className = 'btn btn-sm btn-warning'; }
    }

    function fmt(ms) {
        const totalSec = Math.max(0, Math.floor(ms / 1000));
        const m = Math.floor(totalSec / 60);
        const s = totalSec % 60;
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    function tick() {
        const now = Date.now();
        const effectiveElapsed = paused
            ? (pausedAt - anchorTime - pausedOffset)
            : (now - anchorTime - pausedOffset);
        const remaining = segmentMs - effectiveElapsed;

        if (segRemEl) {
            segRemEl.textContent = fmt(remaining);
            if (remaining <= 0) {
                segRemEl.className = 'fw-bold text-danger fs-4';
            } else if (remaining < 60000) {
                segRemEl.className = 'fw-bold text-danger';
            } else if (remaining < 120000) {
                segRemEl.className = 'fw-bold text-warning';
            } else {
                segRemEl.className = 'fw-bold text-success';
            }
        }

        if (progressEl) {
            const pct = Math.min(100, (effectiveElapsed / segmentMs) * 100);
            progressEl.style.width = pct + '%';
            progressEl.className = 'progress-bar ' + (pct >= 100 ? 'bg-danger' : pct >= 80 ? 'bg-warning' : 'bg-success');
        }

        if (!alerted && remaining <= 0 && alertEl) {
            alertEl.classList.remove('d-none');
            alerted = true;
        }

        if (totalElEl && meetingStarted) {
            const totalMs = now - meetingStarted.getTime();
            totalElEl.textContent = fmt(totalMs);
        }
    }

    tick();
    setInterval(tick, 1000);
})();
