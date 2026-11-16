"""Fixed content shared by forms, models and templates."""

CAMPUS_CHOICES = [
    ("kihumuro", "Kihumuro campus"),
    ("town", "Town campus"),
    ("city", "Mbarara City"),
]

FEEDBACK_CATEGORIES = [
    ("question", "A question about HIV, testing or PrEP"),
    ("idea", "An idea for a talk or event"),
    ("service", "My experience with a service"),
    ("other", "Something else"),
]

# Icon shown next to each feedback category on the "Ask anonymously" form.
FEEDBACK_ICONS = {"question": "help", "idea": "lightbulb", "service": "star", "other": "dots"}

# "tag" links to the directory filtered by that tag; "url_name" links to another page.
TOPICS = [
    {"name": "Testing", "blurb": "Free HIV tests, self-test kits", "icon": "test-tube", "tag": "testing"},
    {"name": "PrEP and PEP", "blurb": "Prevention before and after exposure", "icon": "shield", "tag": "prep"},
    {"name": "Counselling", "blurb": "Talk to someone in confidence", "icon": "message", "tag": "counselling"},
    {"name": "Condoms", "blurb": "Free pick-up points on campus", "icon": "package", "tag": "condoms"},
    {"name": "Peer support", "blurb": "Trained students, no judgment", "icon": "users", "tag": "peer"},
    {"name": "Treatment", "blurb": "HIV care and clinics in Mbarara", "icon": "activity", "tag": "treatment"},
    {"name": "Living with HIV", "blurb": "Support groups, your rights at MUST", "icon": "heart", "tag": "support"},
    {"name": "Exams and leave", "blurb": "Sitting exams later on health grounds", "icon": "graduation",
     "url_name": "portal:topics", "anchor": "#rights"},
    {"name": "Events", "blurb": "Talks, marches, testing days", "icon": "calendar", "url_name": "portal:events"},
    {"name": "Ask anonymously", "blurb": "No name, no login", "icon": "lock", "url_name": "portal:feedback"},
]

# Student rights from the MUST HIV/AIDS Policy (Nov 2019).
RIGHTS = [
    {"clause": "Clause 5.2.1", "title": "No HIV test to get in",
     "text": "MUST does not ask for an HIV test as a condition of admission, and may not treat you differently because of your status."},
    {"clause": "Clause 5.2.2", "title": "Exams at another sitting",
     "text": "If your health keeps you from an exam, you may sit it at another sitting, in line with university regulations."},
    {"clause": "Clause 5.4", "title": "Your status stays private",
     "text": "Test results and health information are kept confidential. Telling anyone your status is your choice, never a requirement."},
]
