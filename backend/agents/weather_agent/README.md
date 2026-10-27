# SUPADSP Specialist Agent — Weather Intelligence
## Complete Architecture, Telemetry Ingestion, Verification & Technical Specification

---

## 1. Executive Summary & System Role

The **Weather Agent** (`backend/agents/weather_agent/`) is a specialist microservice within the **SUPADSP Smart Urban Planning & AI Decision Support Platform**. It serves as the meteorological telemetry authority for the Hyderabad metropolitan region, providing live atmospheric observations, 7-day numerical forecasts, severe weather risk assessments, biometeorological comfort indices, and cross-domain environmental coupling factors for downstream planning agents.

### Primary Responsibilities:
1. **Live Multi-Source Telemetry Ingestion**: Integrates live real-time weather observations via WeatherAPI.com (primary) and Open-Meteo REST API (secondary/fallback) with sub-second retrieval latency.
2. **Local Met-Data Spatial Resolution**: Resolves arbitrary neighborhood queries across 30 pre-warmed Hyderabad urban localities (e.g., Narayanguda, Begumpet, Gachibowli, HITEC City) with automated dynamic geocoding fallback.
3. **Severe Weather & Risk Alerting Engine**: Computes deterministic threshold-based alerts for extreme heatwaves ($\ge 35^\circ\text{C}$, $\ge 40^\circ\text{C}$), convective thunderstorm activity, torrential rain inundation, and high-wind shear ($\ge 35\text{ km/h}$).
4. **Cross-Domain Coupling Telemetry**: Translates raw atmospheric variables into physical impact coefficients consumed by the **Traffic Agent** (roadway pavement friction, drainage inundation), the **Energy Agent** (thermodynamic HVAC cooling load multiplier), and the **Pollution Agent** (atmospheric boundary layer stability, advective pollutant dispersion).
5. **Conversational Question Answering**: Provides natural language question-answering over meteorological telemetry for city operators (`/api/v1/weather/chat`).
6. **Planner Evidence Generation**: Serves contract-compliant meteorological evidence to the **Planner AI Agent** during multi-domain scenario synthesis.

---

## 2. Architecture & Internal Modules

```
backend/agents/weather_agent/
├── __init__.py           # Package marker exposing version
├── main.py               # FastAPI application entry point, route definitions, cross-domain analysis
├── provider.py           # Multi-tier dual-source telemetry provider, geocoding cache, API clients
├── schemas.py            # Pydantic v2 data models, request/response contracts
├── alerts.py             # Deterministic weather alert evaluation and air comfort index engine
├── chat.py               # Regex & keyword natural-language conversational reasoning engine
└── test_weather.py       # Pytest unit and integration test suite
```

### Module Breakdown:
- **`main.py`**: Initializes the FastAPI app (`SUPADSP Weather Agent`, v2.1.0) and defines HTTP endpoints for health probes, current weather, forecasts, alerts, cross-domain scenario analysis, and conversational chat.
- **`provider.py`**: Houses `WeatherProvider` singleton, managing the 180-second in-memory coordinate cache, geocoding lookup, WeatherAPI.com client, Open-Meteo client, and offline baseline fallback.
- **`schemas.py`**: Pydantic v2 contract specifications: `WeatherCurrentResponse`, `WeatherForecastResponse`, `WeatherAlertsResponse`, `WeatherAnalyzeRequest`, and `WeatherAnalyzeResponse`.
- **`alerts.py`**: Implements `generate_weather_alerts()` and `compute_air_comfort()`, translating live metrics into municipal risk indicators.
- **`chat.py`**: Implements `answer_weather_question()`, extracting locality entities and user intent (rain, temperature, wind, air comfort) to formulate grounded natural-language responses.

---

## 3. Data Sources, APIs & Telemetry Variables

### 3.1. External APIs & Ingestion Tiers

| Tier | Source | Mechanism | Authentication | Coverage |
|---|---|---|---|---|
| **Tier 1 (Primary)** | **WeatherAPI.com** | REST JSON endpoint: `/v1/forecast.json?key={KEY}&q={lat},{lon}&days=7&aqi=no&alerts=yes` | API Key (`WEATHERAPI_KEY` in `.env`) | Real-time current conditions, 7-day daily forecast, 24-hour hourly forecast |
| **Tier 2 (Secondary)** | **Open-Meteo API** | REST JSON endpoint: `https://api.open-meteo.com/v1/forecast` | None (100% Free, keyless public endpoint) | Global numerical weather prediction (NWP) model outputs; real-time telemetry, 7-day daily, 24-hour hourly |
| **Geocoding** | **Open-Meteo Geocoding** | REST JSON endpoint: `https://geocoding-api.open-meteo.com/v1/search?name={name}&count=1` | None (Keyless) | Translates any locality name to exact latitude and longitude |
| **Tier 3 (Offline Fallback)** | **Static Verified Baseline** | Local deterministic dictionary in `provider._get_baseline_fallback()` | None (Local execution) | Strictly engaged when network connectivity is severed or external APIs fail |

### 3.2. Retrieved Weather Variables

The agent ingests and exposes the following meteorological variables:

1. **Ambient Temperature (`temperature_c`)**: Measured at 2 meters above ground level ($^\circ\text{C}$).
2. **Relative Humidity (`humidity_pct`)**: Atmospheric water vapor saturation percentage ($0\text{--}100\%$).
3. **Apparent Temperature (`feels_like_c`)**: Heat index factoring moisture and wind.
4. **Precipitation (`precipitation_mm`)**: Surface rainfall accumulation in millimeters ($\text{mm}$).
5. **Wind Speed (`wind_speed_kmh`)**: Horizontal velocity at 10 meters above ground level ($\text{km/h}$).
6. **Wind Direction (`wind_direction`)**: 16-point cardinal compass vector (e.g., `WSW`, `ENE`, `NNE`) converted from raw degrees.
7. **Atmospheric Surface Pressure (`pressure_hpa`)**: Barometric pressure measured in hectopascals ($\text{hPa}$).
8. **Dew Point (`dew_point_c`)**: Condensation temperature ($^\circ\text{C}$) computed via the Magnus-Tetens formula.
9. **UV Index (`uv_index`)**: Solar ultraviolet radiation hazard index ($0\text{--}12+$).
10. **Horizontal Visibility (`visibility_km`)**: Line-of-sight visual range in kilometers.
11. **Weather Condition & Icon (`condition`, `icon`)**: Standardized descriptive text (e.g., `Partly Cloudy`, `Thunderstorm`, `Clear Sky`) and mapped UI icon name.

---

## 4. Machine Learning & Algorithms: What Is Actually Implemented?

### **No Machine Learning or Deep Learning Models Are Used**
> **Important for Viva & Technical Defense**: The Weather Agent **does NOT train or execute any local ML/DL models** (no PyTorch, TensorFlow, Scikit-learn, XGBoost, or neural networks). Forecasts returned by the agent originate from the numerical weather prediction (NWP) physics simulations operated by Open-Meteo (ECMWF, GFS, ICON) and WeatherAPI.com.

### Implemented Deterministic & Physics Algorithms:

#### 1. Magnus-Tetens Dew Point Formulation
When external APIs omit explicit dew point observations, the agent computes it directly from ambient temperature $T$ ($^\circ\text{C}$) and relative humidity $\text{RH}$ ($0\text{--}100\%$):

$$\alpha(T, \text{RH}) = \frac{17.27 \cdot T}{237.7 + T} + \ln\left(\frac{\max(\text{RH}, 1)}{100.0}\right)$$

$$T_{\text{dew}} = \frac{237.7 \cdot \alpha(T, \text{RH})}{17.27 - \alpha(T, \text{RH})}$$

#### 2. Degree-to-Cardinal Wind Direction Conversion
Converts continuous azimuthal degrees ($\theta \in [0^\circ, 360^\circ)$) to 16 compass directions:

$$\text{Index} = \left\lfloor \frac{\theta + 11.25^\circ}{22.5^\circ} \right\rfloor \pmod{16}$$

#### 3. WMO Interpretation Code Mapping
Maps international World Meteorological Organization (WMO) numeric weather codes ($0\text{--}99$) into human-readable descriptions and Lucide icon tokens:
- Code `0`: `Clear Sky` $\rightarrow$ `Sun`
- Code `1, 2`: `Mainly Clear` $\rightarrow$ `Sun`
- Code `3`: `Overcast` $\rightarrow$ `Cloud`
- Code `45, 48`: `Fog` $\rightarrow$ `Cloud`
- Code `51, 53, 55`: `Drizzle` $\rightarrow$ `CloudRain`
- Code `61, 63`: `Moderate Rain` $\rightarrow$ `CloudRain`
- Code `65`: `Heavy Rain` $\rightarrow$ `CloudRain`
- Code `80, 81, 82`: `Rain Showers` $\rightarrow$ `CloudRain`
- Code `95, 96, 99`: `Thunderstorm` $\rightarrow$ `CloudLightning`

#### 4. Deterministic Severe Alert Thresholds (`alerts.py`)
- **Heatwave**:
  - `CRITICAL` alert if $T \ge 40.0^\circ\text{C}$ (extreme heat advisory).
  - `MODERATE` alert if $35.0^\circ\text{C} \le T < 40.0^\circ\text{C}$ (high hydration advisory).
- **Thunderstorm & Monsoon Inundation**:
  - `HIGH` alert if condition contains `"thunder"` or precipitation $> 15.0\text{ mm}$.
  - `MODERATE` watch if 48-hour rain probability $\ge 50\%$ or convective cloud build-up detected.
- **High Wind Advisory**:
  - `MODERATE` advisory if wind speed $\ge 35.0\text{ km/h}$.
- **Baseline**:
  - `LOW` advisory indicating nominal seasonal conditions if no threshold is breached.

#### 5. Cross-Domain Coupling Equations (`main.py`)
- **Traffic Pavement Friction & Speed Reduction**:
  $$\Delta v_{\text{traffic}} = \begin{cases} -15.0\% & \text{if } P > 5.0\text{ mm} \\ -8.0\% & \text{if } 0 < P \le 5.0\text{ mm} \\ 0.0\% & \text{otherwise} \end{cases}$$
  $$\text{Friction} = \begin{cases} \text{LOW} & \text{if } P > 2.0\text{ mm} \\ \text{NORMAL} & \text{otherwise} \end{cases}$$
- **Energy HVAC Demand Factor**:
  $$\text{Cooling Factor} = 1.0 + \max\left(0.0, (T - 25.0^\circ\text{C}) \cdot 0.04\right)$$
  $$\text{HVAC Stress} = \begin{cases} \text{HIGH} & \text{if } T \ge 38.0^\circ\text{C} \\ \text{ELEVATED} & \text{if } 32.0^\circ\text{C} \le T < 38.0^\circ\text{C} \\ \text{NORMAL} & \text{otherwise} \end{cases}$$
- **Pollution Dispersion & Ozone Risk**:
  $$\text{Dispersion} = \begin{cases} \text{POOR} & \text{if } v_{\text{wind}} < 5.0\text{ km/h} \\ \text{FAVORABLE} & \text{if } v_{\text{wind}} > 15.0\text{ km/h} \\ \text{MODERATE} & \text{otherwise} \end{cases}$$
  $$\text{Ozone Risk} = \begin{cases} \text{HIGH} & \text{if } T > 33.0^\circ\text{C} \\ \text{MODERATE} & \text{otherwise} \end{cases}$$

---

## 5. End-to-End Execution Flow

```mermaid
flowchart TD
    A["User Query / API Client"] --> B{"Request Route"}
    
    B -->|Direct Specialist API| C["GET /api/v1/weather/current"]
    B -->|Supervisor Dispatch| D["agent_client.dispatch_agent('weather')"]
    B -->|Conversational Chat| E["POST /api/v1/weather/chat"]
    
    C & D & E --> F["Spatial Location Resolver (resolve_location)"]
    F --> G{"Pre-warmed Registry Match?"}
    G -->|Yes (e.g. 'Narayanguda')| H["Fetch Coordinates from LOCALITY_COORDINATES"]
    G -->|No| I["Open-Meteo Geocoding REST API"]
    I -->|Resolved| J["Cache Coordinates Dynamically"]
    I -->|Network Failure| K["Fallback to Hyderabad Center (17.3850, 78.4867)"]
    
    H & J & K --> L["Cache Check: lat_lon Key (TTL: 180s)"]
    L -->|Cache Hit (< 180s)| M["Return Cached Telemetry"]
    L -->|Cache Miss| N{"WEATHERAPI_KEY Configured?"}
    
    N -->|Yes| O["Call WeatherAPI.com REST API"]
    N -->|No / Failed| P["Call Open-Meteo Free Forecast REST API"]
    O -->|Success| Q["Parse Current, 7-Day & Hourly Arrays"]
    P -->|Success| Q
    O & P -->|Network Outage| R["Return Offline Verified Meteorological Baseline"]
    
    Q & R --> S["Compute Physical Derived Metrics"]
    S --> S1["Dew Point (Magnus-Tetens Formula)"]
    S --> S2["Wind Cardinal Direction (16-point)"]
    S --> S3["Deterministic Severe Alerts (alerts.py)"]
    S --> S4["Air Comfort & Pollen Indices (alerts.py)"]
    S --> S5["Cross-Domain Friction & Cooling Impacts"]
    
    S1 & S2 & S3 & S4 & S5 --> T["Update In-Memory Cache"]
    T --> U["Return Pydantic Response Model"]
```

---

## 6. API Specification & Request/Response Contracts

### Endpoints Overview

| Method | Endpoint | Description | Query / Body Payload | Response Model |
|---|---|---|---|---|
| `GET` | `/health` | Health and active provider status probe | None | `{"agent": "Weather Agent", "status": "ONLINE", ...}` |
| `GET` | `/api/v1/weather/current` | Real-time weather telemetry for locality | `location` (str), `city` (str) | `WeatherCurrentResponse` |
| `GET` | `/api/v1/weather/forecast` | 7-day daily and 24-hour hourly forecasts | `location` (str) | `WeatherForecastResponse` |
| `GET` | `/api/v1/weather/alerts` | Active severe weather alerts & comfort indices | `location` (str) | `WeatherAlertsResponse` |
| `POST` | `/api/v1/weather/analyze` | Cross-domain impacts & planning advisories | `WeatherAnalyzeRequest` | `WeatherAnalyzeResponse` |
| `POST` | `/api/v1/weather/chat` | Natural language weather conversational Q&A | `{"question": str, "location": str}` | JSON Response Dict |

### Realistic Request & Response Example

#### Request:
```http
GET /api/v1/weather/current?location=Narayanguda,%20Hyderabad HTTP/1.1
Host: localhost:8000
Accept: application/json
```

#### Response (`200 OK`):
```json
{
  "source": "Live Open-Meteo API (High-Accuracy Real-Time Telemetry)",
  "provider": "Open-Meteo",
  "is_live": true,
  "timestamp": "2026-10-12T14:30:00Z",
  "city": "Narayanguda",
  "latitude": 17.398,
  "longitude": 78.49,
  "temperature_c": 29.4,
  "humidity_pct": 52,
  "wind_speed_kmh": 11.2,
  "wind_direction": "WSW",
  "precipitation_mm": 0.0,
  "condition": "Mainly Clear",
  "icon": "Sun",
  "feels_like_c": 31.6,
  "dew_point_c": 18.5,
  "pressure_hpa": 1011.8,
  "visibility_km": 10.0,
  "uv_index": 5.4,
  "forecast_7d": [
    {
      "day": "Today",
      "date": "2026-10-12",
      "high": 33,
      "low": 23,
      "condition": "Mainly Clear",
      "rain": "10%",
      "icon": "Sun",
      "max_wind_kmh": 14.5,
      "precipitation_mm": 0.0
    },
    {
      "day": "Tomorrow",
      "date": "2026-10-13",
      "high": 32,
      "low": 24,
      "condition": "Partly Cloudy",
      "rain": "20%",
      "icon": "CloudSun",
      "max_wind_kmh": 12.0,
      "precipitation_mm": 0.5
    }
  ],
  "hourly_temp": [
    {
      "h": "14:00",
      "time": "14:00",
      "temp": 29.4,
      "humidity": 52,
      "pressure": 1011.8,
      "rain_chance": 10,
      "wind_kmh": 11.2
    }
  ],
  "correlations": [
    {
      "param": "Temperature → AQI",
      "correlation": "+0.72",
      "direction": "up",
      "insight": "Ambient temp (29.4°C) accelerates photochemical oxidant synthesis"
    },
    {
      "param": "Wind Speed → Pollutant Dispersion",
      "correlation": "-0.65",
      "direction": "down",
      "insight": "Wind (11.2 km/h WSW) provides advective dispersion of corridor emissions"
    }
  ]
}
```
