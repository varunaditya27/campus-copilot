"""Generate the campus-operations demo data: books.json, book_loans.json,
canteen_menu.json, study_rooms.json, bus_routes.json, lost_found_items.json,
counselling_slots.json and placement_drives.json.

Run from the repository root:  python data/generate_operations_data.py

The output is committed and the script is deterministic, so a re-run reproduces
the same files. Everything is invented for the demo university, shaped by what
the knowledge documents say:

- library.md: eight discussion rooms seating four to eight, a fourteen day loan,
  reference books that do not circulate;
- dining-and-transport.md: the cafeteria's four meals (dinner on weekdays only)
  and its prices (a basic meal about 60 rupees, a full thali 90);
- transportation-routes.md: routes A, B and C with their stops and frequencies,
  and the Saturday town shuttle;
- placement-cell.md: CGPA thresholds between 6.0 and 7.5, at most one active
  backlog, final-year students for full-time drives and pre-final-year students
  for internships.

Book titles and authors are real, well-known textbooks, but the ISBN column holds
placeholder numbers ("DEMO-0001"): the real ISBNs are not in the sources used.
Company names are fictional. There is no counsellor name anywhere.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent
TODAY = date(2026, 10, 15)  # the day the demo data is written for

BOOKS = [
    # (title, author, category, copies, reference only)
    ("Introduction to Algorithms", "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein", "Computer Science", 4, False),
    ("Algorithms", "Robert Sedgewick, Kevin Wayne", "Computer Science", 3, False),
    ("The Art of Computer Programming, Volume 1", "Donald E. Knuth", "Computer Science", 1, True),
    ("Operating System Concepts", "Abraham Silberschatz, Peter B. Galvin, Greg Gagne", "Computer Science", 4, False),
    ("Modern Operating Systems", "Andrew S. Tanenbaum, Herbert Bos", "Computer Science", 2, False),
    ("Computer Networks", "Andrew S. Tanenbaum, David J. Wetherall", "Computer Science", 3, False),
    ("Computer Networking: A Top-Down Approach", "James F. Kurose, Keith W. Ross", "Computer Science", 3, False),
    ("Database System Concepts", "Abraham Silberschatz, Henry F. Korth, S. Sudarshan", "Computer Science", 3, False),
    ("Fundamentals of Database Systems", "Ramez Elmasri, Shamkant B. Navathe", "Computer Science", 2, False),
    ("Artificial Intelligence: A Modern Approach", "Stuart Russell, Peter Norvig", "Artificial Intelligence", 3, False),
    ("Pattern Recognition and Machine Learning", "Christopher M. Bishop", "Artificial Intelligence", 2, False),
    ("Deep Learning", "Ian Goodfellow, Yoshua Bengio, Aaron Courville", "Artificial Intelligence", 2, False),
    ("Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow", "Aurelien Geron", "Artificial Intelligence", 2, False),
    ("Clean Code", "Robert C. Martin", "Software Engineering", 2, False),
    ("Design Patterns", "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides", "Software Engineering", 2, False),
    ("Software Engineering", "Ian Sommerville", "Software Engineering", 3, False),
    ("Computer Organization and Design", "David A. Patterson, John L. Hennessy", "Computer Science", 2, False),
    ("Compilers: Principles, Techniques, and Tools", "Alfred V. Aho, Monica S. Lam, Ravi Sethi, Jeffrey D. Ullman", "Computer Science", 2, False),
    ("Introduction to the Theory of Computation", "Michael Sipser", "Computer Science", 2, False),
    ("Discrete Mathematics and Its Applications", "Kenneth H. Rosen", "Mathematics", 3, False),
    ("Advanced Engineering Mathematics", "Erwin Kreyszig", "Mathematics", 5, False),
    ("Probability and Statistics for Engineers and Scientists", "Ronald E. Walpole, Raymond H. Myers", "Mathematics", 2, False),
    ("Linear Algebra and Its Applications", "Gilbert Strang", "Mathematics", 2, False),
    ("Fundamentals of Physics", "David Halliday, Robert Resnick, Jearl Walker", "Physics", 3, False),
    ("Microelectronic Circuits", "Adel S. Sedra, Kenneth C. Smith", "Electronics", 3, False),
    ("Digital Design", "M. Morris Mano, Michael D. Ciletti", "Electronics", 3, False),
    ("Signals and Systems", "Alan V. Oppenheim, Alan S. Willsky", "Electronics", 2, False),
    ("Digital Signal Processing", "John G. Proakis, Dimitris G. Manolakis", "Electronics", 2, False),
    ("Communication Systems", "Simon Haykin", "Electronics", 2, False),
    ("Electric Machinery Fundamentals", "Stephen J. Chapman", "Electrical", 2, False),
    ("Power System Analysis", "John J. Grainger, William D. Stevenson Jr.", "Electrical", 2, False),
    ("Control Systems Engineering", "Norman S. Nise", "Electrical", 2, False),
    ("Fundamentals of Thermodynamics", "Claus Borgnakke, Richard E. Sonntag", "Mechanical", 2, False),
    ("Fluid Mechanics", "Frank M. White", "Mechanical", 2, False),
    ("Shigley's Mechanical Engineering Design", "Richard G. Budynas, J. Keith Nisbett", "Mechanical", 2, False),
    ("Introduction to Robotics: Mechanics and Control", "John J. Craig", "Robotics", 2, False),
    ("Engineering Mechanics: Statics", "J. L. Meriam, L. G. Kraige", "Mechanical", 3, False),
    ("Concrete Mathematics", "Ronald L. Graham, Donald E. Knuth, Oren Patashnik", "Mathematics", 1, False),
    ("Cryptography and Network Security", "William Stallings", "Cybersecurity", 2, False),
    ("Computer Security: Principles and Practice", "William Stallings, Lawrie Brown", "Cybersecurity", 2, False),
    ("Cloud Computing: Concepts, Technology and Architecture", "Thomas Erl, Ricardo Puttini, Zaigham Mahmood", "Computer Science", 2, False),
    ("Python Crash Course", "Eric Matthes", "Programming", 4, False),
    ("The C Programming Language", "Brian W. Kernighan, Dennis M. Ritchie", "Programming", 4, False),
    ("Effective Java", "Joshua Bloch", "Programming", 2, False),
    ("Data Structures and Algorithm Analysis in C++", "Mark Allen Weiss", "Computer Science", 3, False),
    ("Engineering Ethics", "Charles B. Fleddermann", "Humanities", 2, False),
    ("Technical Communication: Principles and Practice", "Meenakshi Raman, Sangeeta Sharma", "Humanities", 3, False),
    ("Question Papers 2024-25: Computer Science and Engineering", "Examinations Cell", "Reference", 1, True),
    ("Question Papers 2024-25: Electronics and Communication Engineering", "Examinations Cell", "Reference", 1, True),
    ("Handbook of Electrical Engineering", "Various", "Reference", 1, True),
    ("Encyclopedia of Computer Science", "Various", "Reference", 1, True),
]

# Cafeteria hours, from dining-and-transport.md. Items and prices are invented
# around the stated 60 rupee basic meal and 90 rupee thali.
MENU = {
    "breakfast": [
        ("Idli with sambar and chutney", 35, True), ("Masala dosa", 45, True), ("Poha", 30, True),
        ("Upma", 30, True), ("Aloo paratha with curd", 40, True), ("Bread omelette", 40, False),
        ("Puri bhaji", 40, True),
    ],
    "lunch": [
        ("Basic meal: rice or roti, two curries and a side", 60, True), ("Full thali", 90, True),
        ("Veg biryani with raita", 70, True), ("Chicken biryani", 110, False), ("Curd rice", 45, True),
        ("Rajma chawal", 65, True), ("Chapati with paneer curry", 75, True),
    ],
    "evening": [
        ("Tea or coffee", 15, True), ("Samosa", 15, True), ("Veg puff", 20, True), ("Pav bhaji", 50, True),
        ("Vada pav", 25, True), ("Egg puff", 25, False), ("Fruit salad", 40, True),
    ],
    "dinner": [
        ("Basic meal: rice or roti, two curries and a side", 60, True), ("Full thali", 90, True),
        ("Fried rice with manchurian", 75, True), ("Dal khichdi", 55, True), ("Egg curry with rice", 70, False),
        ("Roti with mixed vegetable curry", 60, True), ("Lemon rice with papad", 50, True),
    ],
}

ROUTES = [
    {
        "route_code": "A",
        "name": "City Gate Line",
        "stops": ["Main Gate", "Central Library", "Main Academic Block", "Innovation and Computing Centre", "Hostel Blocks"],
        "service": [
            {"days": [0, 1, 2, 3, 4], "start": "07:00", "end": "09:30", "every_minutes": 20},
            {"days": [0, 1, 2, 3, 4], "start": "09:30", "end": "16:30", "every_minutes": 40},
            {"days": [0, 1, 2, 3, 4], "start": "16:30", "end": "18:30", "every_minutes": 20},
            {"days": [0, 1, 2, 3, 4], "start": "18:30", "end": "20:00", "every_minutes": 40},
            {"days": [5], "start": "07:00", "end": "15:00", "every_minutes": 40},
        ],
        "notes": "Service starts at 7:00 a.m. and runs until 8:00 p.m. on weekdays; the Saturday schedule is reduced and ends at 3:00 p.m. There is no Sunday service.",
    },
    {
        "route_code": "B",
        "name": "Hostel Loop",
        "stops": ["Ashoka Block", "Nilgiri Block", "Kaveri Block", "Vindhya Block", "Student Activity Centre", "Main Academic Block"],
        "service": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "07:00", "end": "22:00", "every_minutes": 15}],
        "notes": "Runs every day including weekends, since hostel residents rely on it regardless of the academic schedule.",
    },
    {
        "route_code": "C",
        "name": "Sports and Recreation Line",
        "stops": ["Main Academic Block", "Innovation and Computing Centre", "Sports Complex"],
        "service": [{"days": [0, 1, 2, 3, 4], "start": "16:00", "end": "20:00", "every_minutes": 30}],
        "notes": "Weekdays only. On weekend tournament days the Transport Office extends service from 8:00 a.m. to 8:00 p.m., every 15 minutes in the two hours before a match, according to the fixture list.",
    },
    {
        "route_code": "TOWN",
        "name": "Saturday Town Shuttle",
        "stops": ["Main Gate", "Town"],
        "service": [{"days": [5], "departures": ["10:00", "16:00"], "returns": ["13:00", "19:00"]}],
        "notes": "Saturdays only, 40 seats a trip allotted first come first served at the security gate.",
    },
]

DISCUSSION_ROOMS = [("DR-1", 4), ("DR-2", 4), ("DR-3", 4), ("DR-4", 6), ("DR-5", 6), ("DR-6", 6), ("DR-7", 8), ("DR-8", 8)]

LOST_ITEMS = [
    ("Black umbrella with a wooden handle", "Main Academic Block, ground floor lobby", -9),
    ("Blue steel water bottle", "Central Cafeteria", -8),
    ("Student ID card (name Karthik)", "Central Library, reference area", -6),
    ("Scientific calculator (Casio fx-991)", "Seminar Hall", -5),
    ("Grey hoodie", "Sports Complex, near the badminton court", -5),
    ("Set of keys on a red keychain", "Innovation and Computing Centre, Computing Lab 1", -3),
    ("Black wireless earphones case", "Route B shuttle", -2),
    ("Spiral notebook with Data Structures notes", "Main Academic Block, Room 214 corridor", -2),
    ("Prescription glasses in a brown case", "Student Activity Centre", -1),
    ("Silver wristwatch", "Central Library, second floor", -1),
]

COMPANIES = [
    # (company, role, kind, days from today, min cgpa, max backlogs, departments, deadline days before)
    ("Northwind Systems", "Software Engineer", "full-time", 12, 7.0, 1, "all", 5),
    ("Bluepeak Analytics", "Data Analyst", "full-time", 20, 7.5, 0, ["Information Science and Engineering", "Computer Science and Engineering"], 7),
    ("Cobalt Labs", "Embedded Systems Engineer", "full-time", 26, 6.5, 1, ["Electronics and Communication Engineering", "Electrical and Electronics Engineering"], 5),
    ("Ironbridge Engineering", "Graduate Engineer Trainee", "full-time", 33, 6.0, 1, ["Mechanical Engineering", "Electrical and Electronics Engineering"], 7),
    ("Lumen Cloud", "Cloud Support Engineer", "full-time", 40, 6.5, 1, "all", 7),
    ("Harbor Digital Services", "Associate Consultant", "full-time", 47, 6.0, 1, "all", 5),
    ("Quantum Loop", "Machine Learning Engineer", "full-time", 55, 7.5, 0, ["Information Science and Engineering", "Computer Science and Engineering"], 7),
    ("Terrace Robotics", "Robotics Engineer", "full-time", 62, 7.0, 1, ["Mechanical Engineering", "Electronics and Communication Engineering"], 7),
    ("Northwind Systems", "Software Engineering Intern", "internship", 18, 6.5, 1, "all", 5),
    ("Signal Forge", "Hardware Design Intern", "internship", 30, 6.0, 1, ["Electronics and Communication Engineering", "Electrical and Electronics Engineering"], 5),
    ("Pinecone Web Studio", "Web Development Intern", "internship", 38, 6.0, 1, ["Information Science and Engineering", "Computer Science and Engineering"], 5),
    ("Ironbridge Engineering", "Manufacturing Intern", "internship", 45, 6.0, 1, ["Mechanical Engineering"], 5),
]


def build_books() -> list[dict]:
    return [
        {
            "book_id": f"BK-{index:04d}",
            "title": title,
            "author": author,
            "isbn": f"DEMO-{index:04d}",
            "category": category,
            "shelf_location": (
                "Reference Area" if reference else f"First floor, shelf {category[:2].upper()}-{(index * 7) % 40 + 1:02d}"
            ),
            "copies_total": copies,
            "reference_only": reference,
        }
        for index, (title, author, category, copies, reference) in enumerate(BOOKS, start=1)
    ]


def build_loans(books: list[dict]) -> list[dict]:
    rng = random.Random(3101)
    students = sorted(s["student_id"] for s in json.loads((DATA / "students.json").read_text()))
    lendable = [b for b in books if not b["reference_only"]]
    loans: list[dict] = []
    borrowers: dict[str, set[str]] = {}

    def lend(book: dict, student_id: str, ago: int) -> None:
        borrowed = TODAY - timedelta(days=ago)
        loans.append(
            {
                "book_id": book["book_id"],
                "student_id": student_id,
                "borrowed_on": borrowed.isoformat(),
                "due_date": (borrowed + timedelta(days=14)).isoformat(),
            }
        )
        borrowers.setdefault(book["book_id"], set()).add(student_id)

    # Every copy of two popular books is out, so there is something to reserve.
    for title in ("Introduction to Algorithms", "Operating System Concepts"):
        book = next(b for b in lendable if b["title"] == title)
        for copy, student_id in enumerate(rng.sample(students, book["copies_total"])):
            lend(book, student_id, 2 + copy * 3)
    # A scatter of other loans, a few of them due soon or overdue.
    for student_id in students:
        for book in rng.sample(lendable, rng.randint(0, 2)):
            if student_id in borrowers.get(book["book_id"], set()):
                continue
            taken = sum(1 for loan in loans if loan["book_id"] == book["book_id"])
            if taken < book["copies_total"] - 1:  # leave a copy on the shelf
                lend(book, student_id, rng.randint(1, 16))
    # Aarav has two books out.
    for title, ago in (("Artificial Intelligence: A Modern Approach", 0), ("Database System Concepts", 12)):
        match = next((b for b in lendable if b["title"] == title), None)
        if match and "1RV23IS101" not in borrowers.get(match["book_id"], set()):
            lend(match, "1RV23IS101", ago)
    return sorted(loans, key=lambda l: (l["book_id"], l["borrowed_on"], l["student_id"]))


def build_menu() -> list[dict]:
    rng = random.Random(3102)
    rows = []
    for weekday in range(6):  # Monday to Saturday; no Sunday menu is published
        for meal, items in MENU.items():
            if meal == "dinner" and weekday == 5:
                continue  # dinner is weekdays only
            always = items[:2] if meal in ("lunch", "dinner") else []
            others = [i for i in items if i not in always]
            for name, price, veg in always + rng.sample(others, 3):
                rows.append({"weekday": weekday, "meal": meal, "item": name, "price": price, "vegetarian": veg})
    return rows


def build_rooms() -> list[dict]:
    return [{"room_id": room, "name": f"Discussion Room {room[3:]}", "capacity": seats, "floor": 2} for room, seats in DISCUSSION_ROOMS]


def build_lost_items() -> list[dict]:
    return [
        {
            "description": description,
            "location_found": place,
            "found_on": (TODAY + timedelta(days=days)).isoformat(),
            "status": "unclaimed",
            "reported_by": None,
        }
        for description, place, days in LOST_ITEMS
    ]


def build_counselling_slots() -> list[dict]:
    slots = []
    day = TODAY + timedelta(days=1)
    while day <= TODAY + timedelta(days=21):
        if day.weekday() < 5:
            for start, end in (("14:00", "14:45"), ("15:00", "15:45"), ("16:00", "16:45")):
                slots.append({"date": day.isoformat(), "start": start, "end": end, "booked_by": None})
        day += timedelta(days=1)
    # A few slots are already taken by other students.
    for index, student_id in ((0, "1RV22CS220"), (4, "1RV24IS219"), (9, "1RV22EC088")):
        slots[index]["booked_by"] = student_id
    return slots


def build_drives() -> list[dict]:
    drives = []
    for index, (company, role, kind, days, cgpa, backlogs, departments, deadline) in enumerate(COMPANIES, start=1):
        on = TODAY + timedelta(days=days)
        drives.append(
            {
                "drive_id": f"PD-{index:03d}",
                "company": company,
                "role": role,
                "kind": kind,
                "date": on.isoformat(),
                "registration_deadline": (on - timedelta(days=deadline)).isoformat(),
                "min_cgpa": cgpa,
                "max_active_backlogs": backlogs,
                "departments": departments,
                "venue": "Seminar Hall" if kind == "full-time" else "Student Activity Centre",
            }
        )
    return drives


def main() -> None:
    books = build_books()
    outputs = {
        "books.json": books,
        "book_loans.json": build_loans(books),
        "canteen_menu.json": build_menu(),
        "study_rooms.json": build_rooms(),
        "bus_routes.json": ROUTES,
        "lost_found_items.json": build_lost_items(),
        "counselling_slots.json": build_counselling_slots(),
        "placement_drives.json": build_drives(),
    }
    for filename, rows in outputs.items():
        (DATA / filename).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print(", ".join(f"{len(rows)} {name.removesuffix('.json')}" for name, rows in outputs.items()))


if __name__ == "__main__":
    main()
