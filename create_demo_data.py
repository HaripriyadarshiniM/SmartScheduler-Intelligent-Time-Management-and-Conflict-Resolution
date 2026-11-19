"""
Demo Data Generator for ChronoSync
Creates a test user with sample events to showcase the scheduling features
"""

from app import get_db, init_db
import hashlib
from datetime import datetime, timedelta
import os

def create_demo_data():
    """Create demo user and sample events"""
    
    # Ensure database directory exists
    os.makedirs('database', exist_ok=True)
    
    # Initialize database
    init_db()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Create demo user
    username = "demo"
    email = "demo@chronosync.app"
    password = "demo123"
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        cursor.execute(
            'INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
            (username, password_hash, email)
        )
        user_id = cursor.lastrowid
        print(f"✓ Created demo user: {username}")
        print(f"  Email: {email}")
        print(f"  Password: {password}")
        print()
    except Exception as e:
        print(f"User might already exist, using existing demo user...")
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        if result:
            user_id = result[0]
        else:
            print("Error creating demo user")
            conn.close()
            return
    
    # Clear existing events for demo user
    cursor.execute('DELETE FROM events WHERE user_id = ?', (user_id,))
    
    # Create sample events
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    sample_events = [
        # Today
        {
            'title': 'Morning Standup',
            'description': 'Daily team sync meeting',
            'start': today + timedelta(hours=9),
            'end': today + timedelta(hours=9, minutes=30),
            'priority': 3,
            'color': '#ff3366',
            'is_deadline': False
        },
        {
            'title': 'Project Review',
            'description': 'Review Q1 project deliverables',
            'start': today + timedelta(hours=10),
            'end': today + timedelta(hours=11, minutes=30),
            'priority': 3,
            'color': '#ff3366',
            'is_deadline': False
        },
        {
            'title': 'Lunch Break',
            'description': 'Team lunch at downtown cafe',
            'start': today + timedelta(hours=12),
            'end': today + timedelta(hours=13),
            'priority': 1,
            'color': '#00ffcc',
            'is_deadline': False
        },
        {
            'title': 'Code Review Session',
            'description': 'Review pull requests and provide feedback',
            'start': today + timedelta(hours=14),
            'end': today + timedelta(hours=15),
            'priority': 2,
            'color': '#ffcc00',
            'is_deadline': False
        },
        
        # Tomorrow
        {
            'title': 'Client Presentation',
            'description': 'Present new features to client stakeholders',
            'start': today + timedelta(days=1, hours=10),
            'end': today + timedelta(days=1, hours=12),
            'priority': 3,
            'color': '#ff3366',
            'is_deadline': False
        },
        {
            'title': 'Design Workshop',
            'description': 'Collaborative design thinking session',
            'start': today + timedelta(days=1, hours=14),
            'end': today + timedelta(days=1, hours=16),
            'priority': 2,
            'color': '#ffcc00',
            'is_deadline': False
        },
        
        # Day after tomorrow
        {
            'title': 'Sprint Planning',
            'description': 'Plan next sprint stories and tasks',
            'start': today + timedelta(days=2, hours=9),
            'end': today + timedelta(days=2, hours=11),
            'priority': 3,
            'color': '#ff3366',
            'is_deadline': False
        },
        {
            'title': 'Documentation Update',
            'description': 'Update API documentation',
            'start': today + timedelta(days=2, hours=15),
            'end': today + timedelta(days=2, hours=17),
            'priority': 1,
            'color': '#00ffcc',
            'is_deadline': False
        },
        
        # Later this week
        {
            'title': 'Team Retrospective',
            'description': 'Reflect on sprint performance',
            'start': today + timedelta(days=4, hours=16),
            'end': today + timedelta(days=4, hours=17),
            'priority': 2,
            'color': '#ffcc00',
            'is_deadline': False
        },
        {
            'title': 'Project Deadline',
            'description': 'Final submission for client project',
            'start': today + timedelta(days=5, hours=17),
            'end': today + timedelta(days=5, hours=18),
            'priority': 3,
            'color': '#ff3366',
            'is_deadline': True
        },
        
        # Next week
        {
            'title': 'One-on-One Meeting',
            'description': 'Weekly sync with manager',
            'start': today + timedelta(days=7, hours=11),
            'end': today + timedelta(days=7, hours=12),
            'priority': 2,
            'color': '#ffcc00',
            'is_deadline': False
        },
        {
            'title': 'Workshop: AI Integration',
            'description': 'Learn about AI tools integration',
            'start': today + timedelta(days=8, hours=13),
            'end': today + timedelta(days=8, hours=15),
            'priority': 1,
            'color': '#00ffcc',
            'is_deadline': False
        },
        
        # Create an intentional conflict to demonstrate optimization
        {
            'title': 'Optional Training Session',
            'description': 'Low priority training that conflicts',
            'start': today + timedelta(hours=10, minutes=30),  # Conflicts with Project Review
            'end': today + timedelta(hours=11),
            'priority': 1,
            'color': '#00ffcc',
            'is_deadline': False
        },
    ]
    
    # Insert events
    for event in sample_events:
        cursor.execute('''
            INSERT INTO events (user_id, title, description, start_time, end_time, priority, is_deadline, color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            event['title'],
            event['description'],
            event['start'].isoformat(),
            event['end'].isoformat(),
            event['priority'],
            event['is_deadline'],
            event['color']
        ))
    
    conn.commit()
    conn.close()
    
    print(f"✓ Created {len(sample_events)} sample events")
    print()
    print("=" * 50)
    print("Demo data created successfully!")
    print("=" * 50)
    print()
    print("Login with:")
    print(f"  Username: {username}")
    print(f"  Password: {password}")
    print()
    print("Features to try:")
    print("  • View events in Month/Week/Day views")
    print("  • Create new events with different priorities")
    print("  • Click 'Optimize Schedule' to resolve conflicts")
    print("  • Filter events by priority")
    print("  • Check the stats panel for insights")
    print()

if __name__ == '__main__':
    create_demo_data()
