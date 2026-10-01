# TimePred — Restaurant Waiting Time Predictor

TimePred is a machine learning system that predicts restaurant customer waiting time using real-time restaurant data, weather conditions, and time-based features.

## How It Works

The backend automatically collects:

- Customers currently in queue
- Employees working
- Average service time
- Orders in the last 30 minutes
- Current hour and day
- Weekend and holiday status
- Temperature and weather conditions

These features are passed to the trained machine learning model:

```text
Restaurant Database ─┐
Time & Holiday Data ─┼──► ML Model ──► Predicted Waiting Time
Weather API ─────────┘
```

## Machine Learning

Several regression models were explored, including:

- Linear Regression
- Polynomial Regression
- Decision Tree
- Random Forest
- K-Nearest Neighbors

The final trained pipeline is saved using `joblib` and loaded by the FastAPI backend.

Model development and evaluation can be found in `app.ipynb`.

## API

The backend is built with FastAPI.

| Endpoint | Purpose |
|---|---|
| `GET /` | Check API status |
| `POST /orders` | Create an order |
| `PUT /orders/{id}/start` | Start an order |
| `PUT /orders/{id}/complete` | Complete an order |
| `PUT /employees` | Update employees working |
| `POST /predict` | Predict waiting time |

The `/predict` endpoint automatically gathers all required features and returns the predicted waiting time.

## Project Structure

```text
├── main.py                  # FastAPI application
├── database.py              # SQLite operations
├── weather.py               # Weather API integration
├── test_main.py             # Automated tests
├── app.ipynb                # ML development
├── waiting_time_model.joblib
├── requirements.txt
└── README.md
```

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn main:app --reload
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

Run automated tests:

```bash
pytest -v
```

## Technologies

Python, FastAPI, SQLite, pandas, scikit-learn, pytest, Pydantic, joblib, Open-Meteo API.

## Future Improvements

- Train on larger real-world datasets
- Improve predictions for unusually long waiting times
- Add a frontend dashboard
- Deploy the API