

from __future__ import annotations as _annotations

import asyncio
import os
import urllib.parse
from dataclasses import dataclass
from typing import Any

import logfire
from devtools import debug
from httpx import AsyncClient

from pydantic_ai import Agent, ModelRetry, RunContext

# 'if-token-present' means nothing will be sent (and the example will work) if you don't have logfire configured
logfire.configure(send_to_logfire='if-token-present')
logfire.instrument_pydantic_ai()


@dataclass
class Deps:
    client: AsyncClient
    weather_api_key: str | None


planner_agent = Agent(
    'openai:gpt-4o',
    # 'Be concise, reply with one sentence.' is enough for some models (like openai) to use
    # the below tools appropriately, but others like anthropic and gemini require a bit more direction.
    instructions=(
        'Ви розумний асистент з планування дня, який дає рекомендації на основі погодних умов. '
        'Будьте лаконічними, відповідайте одним-двома реченнями. '
        'Використовуйте `get_user_location_by_ip` для отримання координат локації, '
        'потім `get_weather` для отримання погоди, '
        'і на основі цієї інформації рекомендуйте оптимальні активності для дня. '
        'Якщо погода гарна, пропонуйте більше заходів на відкритому повітрі. '
        'При поганій погоді, пропонуйте активності в приміщенні. '
        'Враховуйте температуру та опади при плануванні фізичних активностей. '
    ),
    deps_type=Deps,
    retries=2,
)

@planner_agent.tool
async def get_user_location_by_ip(ctx: RunContext[Deps]) -> dict[str, Any]:
    """Get user's location based on their IP address."""
    try:
        # Використання безкоштовного API для визначення місцезнаходження за IP
        r = await ctx.deps.client.get('https://ipapi.co/json/')
        r.raise_for_status()
        data = r.json()
        print(data)

        return {
            'city': data.get('city', 'Unknown'),
            'region': data.get('region', 'Unknown'),
            'country': data.get('country_name', 'Unknown'),
            'lat': data.get('latitude', 0.0),
            'lng': data.get('longitude', 0.0)
        }
    except Exception as e:
        # Якщо виникла помилка, повертаємо значення за замовчуванням (наприклад, Київ)
        logfire.warning(f"Failed to get location by IP: {str(e)}")
        return {
            'city': 'Київ',
            'region': 'Київська область',
            'country': 'Україна',
            'lat': 50.4501,
            'lng': 30.5234
        }

@planner_agent.tool
async def get_weather(ctx: RunContext[Deps], lat: float, lng: float) -> dict[str, Any]:
    """Get the weather at a location.

    Args:
        ctx: The context.
        lat: Latitude of the location.
        lng: Longitude of the location.
    """
    if ctx.deps.weather_api_key is None:
        # if no API key is provided, return a dummy response
        return {'temperature': '21 °C', 'description': 'Sunny'}

    params = {
        'apikey': ctx.deps.weather_api_key,
        'location': f'{lat},{lng}',
        'units': 'metric',
    }
    with logfire.span('calling weather API', params=params) as span:
        r = await ctx.deps.client.get(
            'https://api.tomorrow.io/v4/weather/realtime', params=params
        )
        r.raise_for_status()
        data = r.json()
        span.set_attribute('response', data)

    values = data['data']['values']
    # https://docs.tomorrow.io/reference/data-layers-weather-codes
    code_lookup = {
        1000: 'Clear, Sunny',
        1100: 'Mostly Clear',
        1101: 'Partly Cloudy',
        1102: 'Mostly Cloudy',
        1001: 'Cloudy',
        2000: 'Fog',
        2100: 'Light Fog',
        4000: 'Drizzle',
        4001: 'Rain',
        4200: 'Light Rain',
        4201: 'Heavy Rain',
        5000: 'Snow',
        5001: 'Flurries',
        5100: 'Light Snow',
        5101: 'Heavy Snow',
        6000: 'Freezing Drizzle',
        6001: 'Freezing Rain',
        6200: 'Light Freezing Rain',
        6201: 'Heavy Freezing Rain',
        7000: 'Ice Pellets',
        7101: 'Heavy Ice Pellets',
        7102: 'Light Ice Pellets',
        8000: 'Thunderstorm',
    }
    return {
        'temperature': f'{values["temperatureApparent"]:0.0f}°C',
        'description': code_lookup.get(values['weatherCode'], 'Unknown'),
    }


async def main():
    async with AsyncClient() as client:
        logfire.instrument_httpx(client, capture_all=True)
        # create a free API key at https://www.tomorrow.io/weather-api/
        weather_api_key = os.getenv('WEATHER_API_KEY')
        deps = Deps(
            client=client, weather_api_key=weather_api_key
        )
        result = await planner_agent.run(
            'Допоможи мені спланувати день згідно мого місцезнаходження', deps=deps
        )
        debug(result)
        print('Response:', result.output)


if __name__ == '__main__':
    asyncio.run(main())
