import requests
import os

def get_weather_by_city(city_name: str, api_key: str) -> dict:
    """
    Get current weather information for a given city using OpenWeatherMap API.

    Args:
        city_name (str): Name of the city.
        api_key (str): Your OpenWeatherMap API key.

    Returns:
        dict: Weather information including temperature, description, humidity, etc.
    """
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city_name,
        "appid": api_key,
        "units": "metric"
    }

    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return {
            "city": data.get("name"),
            "temperature_celsius": data["main"]["temp"],
            "description": data["weather"][0]["description"],
            "humidity_percent": data["main"]["humidity"],
            "wind_speed_mps": data["wind"]["speed"]
        }
    else:
        return {
            "error": f"Could not get weather for '{city_name}'. Reason: {response.status_code} - {response.text}"
        }