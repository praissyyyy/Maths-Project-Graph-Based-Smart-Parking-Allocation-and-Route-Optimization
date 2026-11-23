# SmartPark – Gandhipuram: Graph-Based Smart Car Parking Allocation & Route Optimization

> **Academic Program:** Master of Technology (M.Tech) in Cyber Security  
> **Course:** Mathematics for Cyber Security  
> **Study Area:** Gandhipuram, Coimbatore, Tamil Nadu, India  
> **Target Geographic Coordinates:** 11.0182714°N, 76.9677744°E (Radius: 1,400 meters)

---

## 📌 Project Overview

**SmartPark – Gandhipuram** is an end-to-end mathematical optimization and full-stack web reservation platform designed to eliminate urban vehicular cruising and minimize network-wide travel distance in the commercial center of Gandhipuram, Coimbatore.

The system integrates two core components:
1. **Mathematical & Graph-Theoretic Optimization:**
   - Real-world road multigraph extraction from OpenStreetMap ($1,390$ nodes, $3,406$ directed edges).
   - Graph characterization (degree metrics, connectivity, articulation points, bridges, planarity).
   - Three allocation algorithms: **FCFS**, **Nearest Available**, and **Minimum-Cost Maximum-Flow (MCMF)** via Network Simplex.
   - Two routing engines: **Dijkstra's Algorithm** and **A* Search** with an admissible spherical Haversine heuristic.
   - Dynamic discrete-event simulation tracking arrivals, departures, and availability transitions.
2. **Full-Stack Reservation Web Portal:**
   - Interactive UI styled in a modern dark-blue and clean white theme.
   - 8 integrated pages: Home, Find Parking, Facility Details (30 individual slot grid with Green/Red/Yellow indicators), Online Booking, Confirmation with unique Booking IDs, My Bookings with soft cancellations, Interactive Route Map (Leaflet.js + OSM), Admin Analytics Dashboard (Chart.js), and Academic Documentation.
   - ACID-compliant SQLite/SQLAlchemy database preventing overlapping or double bookings.
   - Security controls: PBKDF2 password hashing, RBAC, input sanitization, and parameterized queries.

---

## 📁 Project Directory Structure

```
MATHEMATICS PRAISY PROJECT/
│
├── app.py                         # Application factory & entry point
├── config.py                      # Global configuration parameters
├── database_setup.py              # SQLite seeding & initialization helper
├── requirements.txt               # Complete Python dependencies
├── README.md                      # Comprehensive user & developer guide
├── .env.example                   # Environment configuration template
│
├── models/                        # SQLAlchemy ORM Data Models
│   ├── __init__.py                # Database instance
│   ├── user.py                    # User authentication & RBAC model
│   ├── parking.py                 # ParkingFacility & ParkingSlot models
│   └── booking.py                 # Booking & RouteHistory models
│
├── algorithms/                    # Graph Theory & Optimization Algorithms
│   ├── __init__.py
│   ├── graph_loader.py            # OSMnx downloader & GraphML loader
│   ├── graph_analysis.py          # Degree, SCC, bridges & planarity analysis
│   ├── data_generator.py          # Facilities & vehicle request datasets
│   ├── dijkstra.py                # Priority-queue Dijkstra shortest path
│   ├── astar.py                   # A* search with Haversine heuristic
│   ├── fcfs.py                    # First-Come First-Served allocation
│   ├── nearest_available.py       # Nearest Available greedy allocation
│   ├── mcmf.py                    # Min-Cost Max-Flow flow network model
│   └── allocation.py              # Multi-algorithm comparative orchestrator
│
├── routes/                        # Flask Blueprints & REST API Endpoints
│   ├── __init__.py
│   ├── auth.py                    # Login, register, logout, RBAC decorators
│   ├── parking.py                 # Home, directory, slot layouts, /api/facilities
│   ├── booking.py                 # New booking, confirmation, cancellations
│   ├── map.py                     # Interactive Leaflet map & /api/route engine
│   └── admin.py                   # Admin dashboard, facility edits, audit log
│
├── templates/                     # Jinja2 HTML5 Responsive Web Templates
│   ├── base.html                  # Master layout with navbar and footer
│   ├── index.html                 # Page 1: Landing page with live KPIs
│   ├── parking.html               # Page 2: Facility directory with filters
│   ├── facility_details.html      # Page 3: 30-slot interactive visual layout
│   ├── booking.html               # Page 4: Booking form with overlap checks
│   ├── booking_confirmation.html  # Confirmation receipt with route distance
│   ├── my_bookings.html           # Page 5: User reservations & cancellation
│   ├── map.html                   # Page 6: Leaflet GIS route navigation
│   ├── admin_dashboard.html       # Page 7: Administrator analytics & controls
│   ├── about.html                 # Page 8: Academic methodology documentation
│   ├── login.html                 # Sign-in portal with quick demo buttons
│   └── register.html              # Account registration portal
│
├── static/                        # Web Assets
│   ├── css/
│   │   └── style.css              # Custom responsive styles & slot grid
│   ├── js/
│   │   ├── main.js                # Common client UX interactions
│   │   ├── booking.js             # Dynamic slot availability fetching
│   │   └── map.js                 # Leaflet routing & polyline drawing
│   └── images/
│
├── data/                          # Acquired & Generated Datasets
│   ├── gandhipuram_road_network.graphml  # Real OpenStreetMap road graph
│   ├── parking_facilities.csv     # 5 simulated facilities (P1 to P5)
│   ├── parking_facilities.json    # Nested JSON with 150 slot definitions
│   ├── parking_slots.csv          # Slot metadata and initial statuses
│   ├── vehicle_requests.csv       # Consolidated vehicle requests
│   ├── vehicle_requests_low.csv   # Low demand scenario (10 vehicles)
│   ├── vehicle_requests_medium.csv# Medium demand scenario (25 vehicles)
│   ├── vehicle_requests_high.csv  # High demand scenario (45 vehicles)
│   ├── vehicle_requests_oversubscribed.csv # Oversubscribed (110 vehicles)
│   └── allocation_results.csv     # Experimental assignment records
│
├── experiments/                   # Empirical Evaluation Scripts
│   ├── run_experiments.py         # Multi-scenario benchmarks & chart generation
│   ├── dynamic_simulation.py      # 8-stage arrival/departure simulation
│   └── generate_notebook.py       # Programmatic Colab notebook generator
│
├── notebooks/                     # Academic Google Colab Notebook
│   └── smart_parking_analysis.ipynb # 26-section fully executable notebook
│
├── results/                       # Empirical Outputs & Research Deliverables
│   ├── charts/                    # High-resolution publication figures (300 DPI)
│   ├── csv/                       # Benchmark data tables (allocation, routing, sim)
│   └── reports/                   # Academic project report & graph statistics
│       ├── PROJECT_REPORT.md      # Comprehensive academic report
│       └── graph_statistics.json  # Raw topological properties
│
├── tests/                         # Pytest Automated Test Suite (17 Tests)
│   ├── test_routing.py            # Graph loading, Dijkstra, A*, Haversine
│   ├── test_allocation.py         # FCFS, Nearest Available, MCMF, capacity
│   ├── test_database.py           # Facilities, slots, auth, RBAC, persistence
│   └── test_booking.py            # Bookings, double-booking, overlap, cancel
│
└── instance/
    └── smartpark.db               # SQLite persistent relational database
```

---

## 🚀 Installation and Setup Guide (macOS / Linux)

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 (Python 3.11 recommended)
- `git` and `pip`

### 2. Virtual Environment Setup
Open your terminal in the project directory:
```bash
cd "/Users/praisydevamahimaij/Desktop/MATHEMATICS PRAISY PROJECT"

# Create a virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 💻 Running the Application & Experiments

### 1. Launch the SmartPark Web Application
```bash
export PYTHONPATH=.
python app.py
```
Open your browser and navigate to:  
👉 **http://127.0.0.1:5001**

#### Pre-Seeded Demonstration Accounts:
- **Demo Driver:** `user@smartpark.com` | Password: `User@123`
- **Demo Administrator:** `admin@smartpark.com` | Password: `Admin@123`  
*(Both login credentials can be filled with one click on the Sign In page).*

---

### 2. Execute Pytest Test Suite
To verify all 17 unit and integration tests:
```bash
export PYTHONPATH=.
pytest tests/ -v
```
**Expected Result:** `17 passed in ~3.8s` (100% pass rate).

---

### 3. Run Experimental Benchmarks & Generate Charts
To re-run allocation comparisons across all 4 demand scenarios and shortest-path benchmarks:
```bash
export PYTHONPATH=.
python experiments/run_experiments.py
```
Charts are output to `results/charts/` and data tables to `results/csv/`.

---

### 4. Run Dynamic Parking Simulation
To execute the 8-stage arrival, departure, and reallocation simulation:
```bash
export PYTHONPATH=.
python experiments/dynamic_simulation.py
```
Outputs timeline metrics to `results/csv/dynamic_simulation_timeline.csv` and timeline plot to `results/charts/dynamic_parking_timeline.png`.

---

### 5. Running the Google Colab Notebook
1. Open [Google Colab](https://colab.research.google.com).
2. Click **Upload** and select `notebooks/smart_parking_analysis.ipynb`.
3. Select **Runtime -> Run all**.
4. The notebook self-installs OSMnx, downloads the road network, runs all 26 sections, and outputs charts and tables directly in Colab.

---

## 📊 Summary of Experimental Findings

1. **Allocation Optimality:** Under high vehicular demand (45 vehicles), the **Minimum-Cost Maximum-Flow (MCMF)** optimization reduced overall network travel distance from **$72,576\text{ m}$ (FCFS)** down to **$42,349\text{ m}$ (MCMF)**—an improvement of **41.6%**.
2. **Search State Pruning:** In routing benchmarks across 25+ real Gandhipuram road corridors, **$A^*$ search** explored an average of **$42.8\%$ fewer nodes** than Dijkstra's algorithm while computing mathematically identical shortest routes.
3. **Capacity Non-Violation:** Under oversubscribed demand (110 vehicles competing for 100 available spaces), all algorithms strictly capped assignments at 100 vehicles and marked 10 vehicles unassigned, preventing overcrowding.

---

## 🔒 Academic Integrity & Simulation Notice

- **Road Network:** The road network is authentic and extracted directly from OpenStreetMap within Gandhipuram, Coimbatore.
- **Simulated Facilities:** The 5 parking complexes (P1–P5) and 150 individual slots are simulated models established for academic evaluation and algorithm comparison. They do not represent real-time physical sensor feeds.

---

## 📄 License & Attribution

Developed by **Praisy Deva Mahimai J and Alishiba Dass.** for the **M.Tech Cyber Security** academic project in **Mathematics for Cyber Security** (November 2026).
