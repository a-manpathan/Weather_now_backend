from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# API Endpoints
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Weather codes mapping (from Open-Meteo docs)
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

# Simple activity suggestions
def suggest_activity(weathercode):
    if weathercode in [0, 1]:
        return "Great time for an outdoor walk or cycling!"
    elif weathercode in [2, 3]:
        return "Perfect for a coffee outside or light exercise."
    elif weathercode in [61, 63, 65, 80, 81, 82]:
        return "Stay in and enjoy reading, movies, or indoor hobbies."
    elif weathercode in [71, 73, 75]:
        return "Good day for indoor warmth – maybe hot chocolate!"
    else:
        return "Check conditions carefully before going out."

@app.route("/suggestions", methods=["GET"])
def get_suggestions():
    query = request.args.get("q")
    if not query or len(query) < 2:
        return jsonify({"suggestions": []})

    geo_params = {"name": query, "count": 5}
    try:
        geo_response = requests.get(GEOCODING_URL, params=geo_params).json()
    except requests.exceptions.RequestException:
        return jsonify({"suggestions": []})

    suggestions = []
    if "results" in geo_response:
        for result in geo_response["results"][:5]:
            city_info = {
                "name": result["name"],
                "country": result.get("country", ""),
                "admin1": result.get("admin1", ""),
                "display": f"{result['name']}, {result.get('admin1', '')}, {result.get('country', '')}".replace(", , ", ", ").rstrip(", ")
            }
            suggestions.append(city_info)
    
    return jsonify({"suggestions": suggestions})

@app.route("/weather", methods=["GET"])
def get_weather():
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "City parameter is required"}), 400

    # Step 1: Get latitude & longitude
    geo_params = {"name": city}
    try:
        geo_response = requests.get(GEOCODING_URL, params=geo_params).json()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Geocoding API request failed: {e}"}), 500

    if "results" not in geo_response or len(geo_response["results"]) == 0:
        return jsonify({"error": "City not found"}), 404

    lat = geo_response["results"][0]["latitude"]
    lon = geo_response["results"][0]["longitude"]
    city_name = geo_response["results"][0]["name"]

    # Step 2: Get weather (past week + current + forecast)
    weather_params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weathercode,windspeed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weathercode,windspeed_10m_max",
        "forecast_days": 7,
        "past_days": 7,
        "timezone": "auto"
    }

    try:
        weather_response = requests.get(WEATHER_URL, params=weather_params).json()
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Weather API request failed: {e}"}), 500

    if "current" not in weather_response or "daily" not in weather_response:
        return jsonify({"error": "Weather data not available"}), 500

    # Current weather
    current_data = weather_response["current"]
    current_code = current_data["weathercode"]
    current_weather = {
        "temperature_c": current_data["temperature_2m"],
        "humidity_percent": current_data["relative_humidity_2m"],
        "windspeed_kmh": current_data["windspeed_10m"],
        "condition": WEATHER_CODES.get(current_code, "Unknown"),
        "activity_suggestion": suggest_activity(current_code)
    }

    # Past 7 days
    past_weather = []
    daily_data = weather_response["daily"]
    for i in range(len(daily_data["time"])):
        code = daily_data["weathercode"][i]
        day_data = {
            "date": daily_data["time"][i],
            "max_temp_c": daily_data["temperature_2m_max"][i],
            "min_temp_c": daily_data["temperature_2m_min"][i],
            "max_windspeed_kmh": daily_data["windspeed_10m_max"][i],
            "weathercode": code
        }
        past_weather.append(day_data)

    # Only keep last 7 days separate from forecast
    past_weather = past_weather[:7]  # first 7 entries = past days
    daily_forecasts = past_weather[7:]  # rest = forecast

    # Final response
    result = {
        "city": city_name,
        "latitude": lat,
        "longitude": lon,
        "current_weather": current_weather,
        "past_weather": past_weather,
        "daily_weather": daily_forecasts
    }

    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)