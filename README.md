# SmartScheduler – Intelligent Time Management and Conflict Resolution

## About the Project

SmartScheduler is a web-based time management application developed to help users organize events, manage schedules, detect scheduling conflicts, and improve productivity.

The application uses priority-based scheduling logic to identify overlapping events and automatically reschedule lower-priority events when possible.

## Features

- **User Management:** User registration, login and logout.
- **Event Management:** Create, view, update and delete scheduled events.
- **Conflict Detection:** Identify overlapping events before saving.
- **Priority-Based Scheduling:** Handle scheduling conflicts based on event priorities.
- **Schedule Optimization:** Find alternative time slots and reschedule conflicting events.
- **User Preferences:** Configure working hours, timezone and reminder settings.
- **Availability Management:** Save user availability.
- **Activity Log:** Track user activities.
- **Email Notifications:** Send event confirmations, reminders and delay notifications when SMTP is configured.

## Technologies Used

- **Backend:** Python, Flask
- **Database:** SQLite3
- **Frontend:** HTML5, CSS3, JavaScript
- **Communication:** REST API, JSON
- **Email:** SMTP

## Project Structure

```text
SmartScheduler/
│
├── app.py
├── app.js
├── create_demo_data.py
├── mydb.py
├── requirements.txt
├── start.bat
├── styles.css
│
├── templates/
│   └── index.html
│
└── README.md
```

## Installation and Setup

1. Clone the repository:

```bash
git clone https://github.com/HaripriyadarshiniM/SmartScheduler-Intelligent-Time-Management-and-Conflict-Resolution.git
```

2. Navigate to the project folder:

```bash
cd SmartScheduler-Intelligent-Time-Management-and-Conflict-Resolution
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

4. Run the application:

```bash
python app.py
```

5. Open the application in your browser at:

```text
http://127.0.0.5:5000
```

## Future Enhancements

- Machine learning-based scheduling recommendations.
- Integration with Google Calendar and Outlook.
- Mobile application support.
- Natural language-based event creation.
- Multi-user collaboration and advanced analytics.

## Author

**Haripriyadarshini M**

GitHub: [HaripriyadarshiniM](https://github.com/HaripriyadarshiniM)

---

*SmartScheduler – Organize your time, manage your priorities, and resolve scheduling conflicts efficiently.*
