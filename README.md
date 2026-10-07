# TimePred — Restaurant Waiting Time Predictor

TimePred predicts how long a restaurant customer will wait. It combines the live order queue, staffing, weather, and time-based features, and serves the result through a FastAPI backend and a React dashboard.

## How It Works

```text
React UI ──HTTP + SSE──► FastAPI ──SQL──► SQLite (orders, restaurants)
                            │
                            ├──► Open-Meteo (weather + timezone from coordinates)
                            └──► ML model (scikit-learn pipeline)
```

- **SQLite** is the only place state is stored. The "queue" is not a table: it is calculated by counting orders by `status`.
- **FastAPI** validates requests, changes order state, builds the model input, and announces changes.
- **React** only displays what the API returns. With no backend configured it runs in demo mode.

### Order lifecycle

```text
CREATED ──start──► IN_PROGRESS ──complete──► COMPLETED
```

Transitions are guarded in SQL (`UPDATE ... WHERE status = ?`), so an order cannot be started twice or skipped ahead. An invalid transition returns `409 Conflict`.

## Model Features

The backend gathers these automatically for every prediction:

- Customers waiting in the queue
- Employees working
- Average service time (last 20 completed orders)
- Orders created in the last 30 minutes
- Hour of day and day of week (in the restaurant's local timezone)
- Weekend and holiday flags
- Temperature and weather condition (from the restaurant's coordinates)

The trained pipeline is saved with `joblib`. Model development is in `app.ipynb`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /` | Check API status |
| `POST /orders` | Create an order (returns `id` and `status`) |
| `PUT /orders/{id}/start` | Move an order to `IN_PROGRESS` |
| `PUT /orders/{id}/complete` | Move an order to `COMPLETED` |
| `GET /orders/{id}/status` | Customer tracking: status, orders ahead, ETA |
| `GET /queue` | Today's orders and staff count |
| `PUT /employees` | Update employees working |
| `PUT /restaurant/location` | Save latitude/longitude and resolve the timezone |
| `POST /predict` | Predict waiting time (optional `latitude`, `longitude`) |
| `GET /analytics/hourly` | Typical orders and waits by hour of day |
| `GET /events` | Server-Sent Events stream for live UI updates |

Interactive docs: `http://127.0.0.1:8000/docs`

## Project Structure

```text
├── main.py                  # FastAPI routes
├── schemas.py               # Request/response models (Pydantic)
├── database.py              # SQLite schema and queries
├── prediction.py            # Builds model input and predicts
├── weather.py               # Weather + timezone from coordinates
├── events.py                # Change signal for Server-Sent Events
├── test_main.py             # Automated tests
├── app.ipynb                # ML development
├── waiting_time_model.joblib
├── requirements.txt
└── frontend/                # React + Vite + Tailwind dashboard
    ├── src/App.jsx          # Restaurant and Customer views
    └── .env.example         # Backend URL
```

## Run Locally

### Backend

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

Requires Node.js (LTS).

```bash
cd frontend
cp .env.example .env     # VITE_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open `http://localhost:5173`. Remove `VITE_API_URL` from `.env` to run the UI in demo mode without a backend.

### Tests

```bash
pytest -v
```

Tests use their own database file (`test_restaurant.db`) and never touch real data.

## Technologies

Python, FastAPI, SQLite, pandas, scikit-learn, pytest, Pydantic, joblib, httpx, Open-Meteo API, React, Vite, Tailwind CSS, Recharts, Lucide.
ß