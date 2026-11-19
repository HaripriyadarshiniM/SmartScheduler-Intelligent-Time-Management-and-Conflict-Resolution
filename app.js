// Global state
let currentDate = new Date();
let currentView = 'month';
let events = [];
let selectedDate = null;
let editingEventId = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
});

// Check authentication
function checkAuth() {
    fetch('/api/events')
        .then(response => {
            if (response.ok) {
                document.getElementById('authModal').style.display = 'none';
                document.getElementById('mainApp').classList.remove('hidden');
                loadUserData();
            } else {
                document.getElementById('authModal').style.display = 'flex';
            }
        })
        .catch(() => {
            document.getElementById('authModal').style.display = 'flex';
        });
}

// Setup event listeners
function setupEventListeners() {
    // Auth tabs
    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab + 'Form').classList.add('active');
        });
    });

    // Login form
    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (response.ok) {
                showAuthMessage('Login successful!', 'success');
                setTimeout(() => {
                    document.getElementById('authModal').style.display = 'none';
                    document.getElementById('mainApp').classList.remove('hidden');
                    loadUserData();
                }, 1000);
            } else {
                showAuthMessage(data.error || 'Login failed', 'error');
            }
        } catch (error) {
            showAuthMessage('Network error', 'error');
        }
    });

    // Register form
    document.getElementById('registerForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('registerUsername').value;
        const email = document.getElementById('registerEmail').value;
        const password = document.getElementById('registerPassword').value;

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });

            const data = await response.json();

            if (response.ok) {
                showAuthMessage('Account created! Logging you in...', 'success');
                setTimeout(() => {
                    document.getElementById('authModal').style.display = 'none';
                    document.getElementById('mainApp').classList.remove('hidden');
                    loadUserData();
                }, 1000);
            } else {
                showAuthMessage(data.error || 'Registration failed', 'error');
            }
        } catch (error) {
            showAuthMessage('Network error', 'error');
        }
    });

    // Logout
    document.getElementById('logoutBtn').addEventListener('click', async () => {
        await fetch('/api/logout', { method: 'POST' });
        location.reload();
    });

    // Calendar navigation
    document.getElementById('prevBtn').addEventListener('click', () => {
        if (currentView === 'month') {
            currentDate.setMonth(currentDate.getMonth() - 1);
        } else if (currentView === 'week') {
            currentDate.setDate(currentDate.getDate() - 7);
        } else {
            currentDate.setDate(currentDate.getDate() - 1);
        }
        renderCalendar();
    });

    document.getElementById('nextBtn').addEventListener('click', () => {
        if (currentView === 'month') {
            currentDate.setMonth(currentDate.getMonth() + 1);
        } else if (currentView === 'week') {
            currentDate.setDate(currentDate.getDate() + 7);
        } else {
            currentDate.setDate(currentDate.getDate() + 1);
        }
        renderCalendar();
    });

    document.getElementById('todayBtn').addEventListener('click', () => {
        currentDate = new Date();
        renderCalendar();
    });

    // View toggle
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentView = btn.dataset.view;
            renderCalendar();
        });
    });

    // Add event button
    document.getElementById('addEventBtn').addEventListener('click', () => {
        openEventModal();
    });

    // Event form
    document.getElementById('eventForm').addEventListener('submit', saveEvent);

    // Optimize button
    document.getElementById('optimizeBtn').addEventListener('click', optimizeSchedule);

    // Priority filters
    document.querySelectorAll('.priority-checkbox input').forEach(checkbox => {
        checkbox.addEventListener('change', renderCalendar);
    });
}

// Show auth message
function showAuthMessage(message, type) {
    const messageDiv = document.getElementById('authMessage');
    messageDiv.textContent = message;
    messageDiv.className = `auth-message ${type}`;
    messageDiv.style.display = 'block';

    setTimeout(() => {
        messageDiv.style.display = 'none';
    }, 5000);
}

// Load user data
async function loadUserData() {
    try {
        const response = await fetch('/api/events');
        if (response.ok) {
            events = await response.json();
            renderCalendar();
            updateStats();
        }
    } catch (error) {
        console.error('Error loading events:', error);
    }
}

// Render calendar
function renderCalendar() {
    document.getElementById('calendarGrid').classList.toggle('hidden', currentView !== 'month');
    document.getElementById('weekView').classList.toggle('hidden', currentView !== 'week');
    document.getElementById('dayView').classList.toggle('hidden', currentView !== 'day');

    updateCalendarTitle();

    if (currentView === 'month') {
        renderMonthView();
    } else if (currentView === 'week') {
        renderWeekView();
    } else {
        renderDayView();
    }
}

// Update calendar title
function updateCalendarTitle() {
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    
    let title = '';
    if (currentView === 'month') {
        title = `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
    } else if (currentView === 'week') {
        const weekStart = getWeekStart(currentDate);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);
        title = `${monthNames[weekStart.getMonth()]} ${weekStart.getDate()} - ${monthNames[weekEnd.getMonth()]} ${weekEnd.getDate()}, ${weekStart.getFullYear()}`;
    } else {
        title = `${monthNames[currentDate.getMonth()]} ${currentDate.getDate()}, ${currentDate.getFullYear()}`;
    }
    
    document.getElementById('currentMonthYear').textContent = title;
}

// Render month view
function renderMonthView() {
    const calendar = document.getElementById('calendarGrid');
    calendar.innerHTML = '';

    // Day headers
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    dayNames.forEach(day => {
        const header = document.createElement('div');
        header.className = 'calendar-day-header';
        header.textContent = day;
        calendar.appendChild(header);
    });

    // Get first day of month
    const firstDay = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const lastDay = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
    
    // Calculate padding days
    const startPadding = firstDay.getDay();
    const endPadding = 6 - lastDay.getDay();

    // Previous month days
    for (let i = startPadding - 1; i >= 0; i--) {
        const date = new Date(firstDay);
        date.setDate(date.getDate() - i - 1);
        renderDay(calendar, date, true);
    }

    // Current month days
    for (let day = 1; day <= lastDay.getDate(); day++) {
        const date = new Date(currentDate.getFullYear(), currentDate.getMonth(), day);
        renderDay(calendar, date, false);
    }

    // Next month days
    for (let i = 1; i <= endPadding; i++) {
        const date = new Date(lastDay);
        date.setDate(date.getDate() + i);
        renderDay(calendar, date, true);
    }
}

// Render individual day
function renderDay(calendar, date, otherMonth) {
    const dayDiv = document.createElement('div');
    dayDiv.className = 'calendar-day';
    
    if (otherMonth) {
        dayDiv.classList.add('other-month');
    }
    
    // Check if today
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
        dayDiv.classList.add('today');
    }

    // Day number
    const dayNumber = document.createElement('div');
    dayNumber.className = 'day-number';
    dayNumber.textContent = date.getDate();
    dayDiv.appendChild(dayNumber);

    // Events for this day
    const dayEvents = document.createElement('div');
    dayEvents.className = 'day-events';
    
    const filteredEvents = getFilteredEvents();
    const dateStr = date.toISOString().split('T')[0];
    
    filteredEvents.forEach(event => {
        const eventStart = new Date(event.start);
        const eventDateStr = eventStart.toISOString().split('T')[0];
        
        if (eventDateStr === dateStr) {
            const eventPill = document.createElement('div');
            eventPill.className = 'event-pill';
            eventPill.style.borderLeftColor = event.color;
            eventPill.textContent = event.title;
            eventPill.addEventListener('click', (e) => {
                e.stopPropagation();
                openEventModal(event);
            });
            dayEvents.appendChild(eventPill);
        }
    });
    
    dayDiv.appendChild(dayEvents);
    
    dayDiv.addEventListener('click', () => {
        selectedDate = date;
        openEventModal();
    });
    
    calendar.appendChild(dayDiv);
}

// Render week view
function renderWeekView() {
    const weekView = document.getElementById('weekView');
    weekView.innerHTML = '';

    const weekStart = getWeekStart(currentDate);
    
    // Time slots
    for (let hour = 0; hour < 24; hour++) {
        const timeSlot = document.createElement('div');
        timeSlot.className = 'time-slot';
        timeSlot.textContent = `${hour.toString().padStart(2, '0')}:00`;
        weekView.appendChild(timeSlot);

        // Day slots
        for (let day = 0; day < 7; day++) {
            const daySlot = document.createElement('div');
            daySlot.className = 'week-day-slot';
            
            const date = new Date(weekStart);
            date.setDate(date.getDate() + day);
            date.setHours(hour);
            
            // Add events for this hour
            const filteredEvents = getFilteredEvents();
            filteredEvents.forEach(event => {
                const eventStart = new Date(event.start);
                if (eventStart.toDateString() === date.toDateString() &&
                    eventStart.getHours() === hour) {
                    const eventDiv = document.createElement('div');
                    eventDiv.className = 'event-pill';
                    eventDiv.style.borderLeftColor = event.color;
                    eventDiv.textContent = event.title;
                    eventDiv.addEventListener('click', () => openEventModal(event));
                    daySlot.appendChild(eventDiv);
                }
            });
            
            weekView.appendChild(daySlot);
        }
    }
}

// Render day view
function renderDayView() {
    const dayView = document.getElementById('dayView');
    dayView.innerHTML = '';

    for (let hour = 0; hour < 24; hour++) {
        const timeSlot = document.createElement('div');
        timeSlot.className = 'time-slot';
        timeSlot.textContent = `${hour.toString().padStart(2, '0')}:00`;
        dayView.appendChild(timeSlot);

        const daySlot = document.createElement('div');
        daySlot.className = 'week-day-slot';
        
        const date = new Date(currentDate);
        date.setHours(hour);
        
        const filteredEvents = getFilteredEvents();
        filteredEvents.forEach(event => {
            const eventStart = new Date(event.start);
            if (eventStart.toDateString() === date.toDateString() &&
                eventStart.getHours() === hour) {
                const eventDiv = document.createElement('div');
                eventDiv.className = 'event-pill';
                eventDiv.style.borderLeftColor = event.color;
                eventDiv.textContent = event.title;
                eventDiv.addEventListener('click', () => openEventModal(event));
                daySlot.appendChild(eventDiv);
            }
        });
        
        dayView.appendChild(daySlot);
    }
}

// Get week start date
function getWeekStart(date) {
    const d = new Date(date);
    const day = d.getDay();
    const diff = d.getDate() - day;
    return new Date(d.setDate(diff));
}

// Get filtered events
function getFilteredEvents() {
    const priorities = [];
    document.querySelectorAll('.priority-checkbox input:checked').forEach(checkbox => {
        priorities.push(parseInt(checkbox.dataset.priority));
    });
    
    return events.filter(event => priorities.includes(event.priority));
}

// Open event modal
function openEventModal(event = null) {
    editingEventId = event ? event.id : null;
    
    const modal = document.getElementById('eventModal');
    const title = document.getElementById('eventModalTitle');
    const deleteBtn = document.getElementById('deleteEventBtn');
    
    if (event) {
        title.textContent = 'Edit Event';
        deleteBtn.classList.remove('hidden');
        
        document.getElementById('eventId').value = event.id;
        document.getElementById('eventTitle').value = event.title;
        document.getElementById('eventDescription').value = event.description || '';
        document.getElementById('eventStart').value = formatDateTimeLocal(event.start);
        document.getElementById('eventEnd').value = formatDateTimeLocal(event.end);
        document.getElementById('eventPriority').value = event.priority;
        document.getElementById('eventColor').value = event.color;
        document.getElementById('eventDeadline').checked = event.is_deadline;
    } else {
        title.textContent = 'New Event';
        deleteBtn.classList.add('hidden');
        
        document.getElementById('eventForm').reset();
        document.getElementById('eventId').value = '';
        
        if (selectedDate) {
            const startDate = new Date(selectedDate);
            startDate.setHours(9, 0);
            const endDate = new Date(selectedDate);
            endDate.setHours(10, 0);
            
            document.getElementById('eventStart').value = formatDateTimeLocal(startDate.toISOString());
            document.getElementById('eventEnd').value = formatDateTimeLocal(endDate.toISOString());
        }
    }
    
    modal.classList.remove('hidden');
    
    // Setup delete button
    deleteBtn.onclick = () => deleteEvent(event.id);
}

// Close event modal
function closeEventModal() {
    document.getElementById('eventModal').classList.add('hidden');
    editingEventId = null;
    selectedDate = null;
}

// Format datetime for input
function formatDateTimeLocal(isoString) {
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Save event
async function saveEvent(e) {
    e.preventDefault();
    
    const eventData = {
        title: document.getElementById('eventTitle').value,
        description: document.getElementById('eventDescription').value,
        start: new Date(document.getElementById('eventStart').value).toISOString(),
        end: new Date(document.getElementById('eventEnd').value).toISOString(),
        priority: parseInt(document.getElementById('eventPriority').value),
        is_deadline: document.getElementById('eventDeadline').checked,
        color: document.getElementById('eventColor').value
    };
    
    try {
        let response;
        if (editingEventId) {
            response = await fetch(`/api/events/${editingEventId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(eventData)
            });
        } else {
            response = await fetch('/api/events', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(eventData)
            });
        }
        
        if (response.ok) {
            showNotification(editingEventId ? 'Event updated!' : 'Event created!');
            closeEventModal();
            loadUserData();
        } else {
            showNotification('Failed to save event', 'error');
        }
    } catch (error) {
        showNotification('Network error', 'error');
    }
}

// Delete event
async function deleteEvent(eventId) {
    if (!confirm('Are you sure you want to delete this event?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/events/${eventId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Event deleted!');
            closeEventModal();
            loadUserData();
        } else {
            showNotification('Failed to delete event', 'error');
        }
    } catch (error) {
        showNotification('Network error', 'error');
    }
}

// Optimize schedule
async function optimizeSchedule() {
    try {
        showNotification('Analyzing schedule...');

        const response = await fetch('/api/optimize', { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            showOptimizeModal(data);
            loadUserData();
        } else {
            showNotification('Optimization failed', 'error');
        }
    } catch (error) {
        console.error('Optimization error:', error);
        showNotification('Network error', 'error');
    }
}

function showOptimizeModal(data) {
    const rescheduled = data.rescheduled || [];
    const conflicts   = data.conflicts   || [];

    // Summary stats
    const summaryEl = document.getElementById('optimizeSummary');
    summaryEl.innerHTML = `
        <div class="opt-stat">
            <div class="opt-stat-num">${conflicts.length}</div>
            <div class="opt-stat-label">Conflicts Found</div>
        </div>
        <div class="opt-stat">
            <div class="opt-stat-num">${rescheduled.length}</div>
            <div class="opt-stat-label">Events Rescheduled</div>
        </div>
        <div class="opt-stat">
            <div class="opt-stat-num">${rescheduled.length > 0 ? '✓' : '—'}</div>
            <div class="opt-stat-label">Schedule Optimized</div>
        </div>
    `;

    // Conflicts section
    const conflictsSection = document.getElementById('optimizeConflictsSection');
    const conflictsList    = document.getElementById('optimizeConflictsList');
    if (conflicts.length > 0) {
        conflictsList.innerHTML = conflicts.map(c => `
            <div class="opt-conflict-card">
                <div class="opt-conflict-title">⚠️ ${escapeHtml(c.event1 || '')} &amp; ${escapeHtml(c.event2 || '')}</div>
                <div class="opt-conflict-meta">${c.detail || 'Overlapping time slots detected'}</div>
            </div>
        `).join('');
        conflictsSection.classList.remove('hidden');
    } else {
        conflictsSection.classList.add('hidden');
    }

    // Rescheduled section
    const reschedSection = document.getElementById('optimizeRescheduledSection');
    const reschedList    = document.getElementById('optimizeRescheduledList');
    if (rescheduled.length > 0) {
        reschedList.innerHTML = rescheduled.map(item => {
            const oldDate = new Date(item.old_start);
            const newDate = new Date(item.new_start);
            const fmt = d => d.toLocaleString(undefined, { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
            return `
                <div class="opt-reschedule-card">
                    <div class="opt-reschedule-title">
                        <span style="color:var(--accent)">📅</span>
                        ${escapeHtml(item.title)}
                        ${item.priority ? `<span style="font-size:11px;background:var(--surface);border:1px solid var(--border);border-radius:5px;padding:2px 7px;font-weight:500;color:var(--text-muted)">${item.priority}</span>` : ''}
                    </div>
                    <div class="opt-time-row">
                        <span style="color:var(--text-muted);font-size:11px;">From</span>
                        <span class="opt-time-badge" style="color:#f87171;">${fmt(oldDate)}</span>
                        <span class="opt-arrow">→</span>
                        <span class="opt-time-badge" style="color:#34d399;">${fmt(newDate)}</span>
                    </div>
                </div>
            `;
        }).join('');
        reschedSection.classList.remove('hidden');
    } else {
        reschedSection.classList.add('hidden');
    }

    // No-conflicts message
    const noConflicts = document.getElementById('optimizeNoConflicts');
    if (conflicts.length === 0 && rescheduled.length === 0) {
        noConflicts.classList.remove('hidden');
        document.getElementById('optimizeModalTitle').textContent = '✅ Schedule Optimized';
    } else {
        noConflicts.classList.add('hidden');
        document.getElementById('optimizeModalTitle').textContent = '⚡ Optimization Results';
    }

    document.getElementById('optimizeModal').classList.remove('hidden');
}

function closeOptimizeModal() {
    document.getElementById('optimizeModal').classList.add('hidden');
}

function escapeHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Helper function to format datetime for display
function formatDateTime(date) {
    const options = { 
        weekday: 'short', 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleString('en-US', options);
}

// Show notification
function showNotification(message) {
    const notification = document.getElementById('notification');
    document.getElementById('notificationText').textContent = message;
    notification.classList.remove('hidden');
    
    setTimeout(() => {
        notification.classList.add('hidden');
    }, 3000);
}

// Update stats
function updateStats() {
    const now = new Date();
    const weekStart = getWeekStart(now);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 7);
    
    const weekEvents = events.filter(event => {
        const eventDate = new Date(event.start);
        return eventDate >= weekStart && eventDate < weekEnd;
    });
    
    document.getElementById('totalEvents').textContent = weekEvents.length;
    
    // Calculate total hours
    let totalHours = 0;
    weekEvents.forEach(event => {
        const start = new Date(event.start);
        const end = new Date(event.end);
        totalHours += (end - start) / (1000 * 60 * 60);
    });
    document.getElementById('totalHours').textContent = totalHours.toFixed(1);
    
    // Count conflicts in ALL events (not just this week)
    let conflicts = 0;
    for (let i = 0; i < events.length; i++) {
        for (let j = i + 1; j < events.length; j++) {
            const start1 = new Date(events[i].start);
            const end1 = new Date(events[i].end);
            const start2 = new Date(events[j].start);
            const end2 = new Date(events[j].end);
            
            // Check if events overlap
            if (start1 < end2 && start2 < end1) {
                conflicts++;
                console.log(`Conflict: "${events[i].title}" overlaps "${events[j].title}"`);
            }
        }
    }
    
    const conflictElement = document.getElementById('conflictCount');
    conflictElement.textContent = conflicts;
    
    // Visual feedback
    if (conflicts > 0) {
        conflictElement.style.color = 'var(--danger)';
    } else {
        conflictElement.style.color = 'var(--success)';
    }
}
