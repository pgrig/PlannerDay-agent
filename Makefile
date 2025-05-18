.PHONY: build run stop clean logs shell test env help

# Variables
APP_NAME = plannerday-agent
DOCKER_COMPOSE = docker compose

help:
	@echo "Available commands:"
	@echo "  make build    - Build the Docker image"
	@echo "  make run      - Run the application in Docker"
	@echo "  make stop     - Stop the running container"
	@echo "  make clean    - Remove containers and images"
	@echo "  make logs     - Show logs from the container"
	@echo "  make shell    - Open a shell in the container"
	@echo "  make test     - Run tests in the container"
	@echo "  make env      - Create an .env file template if it doesn't exist"

build:
	$(DOCKER_COMPOSE) build

run:
	$(DOCKER_COMPOSE) up -d

stop:
	$(DOCKER_COMPOSE) down

clean: stop
	$(DOCKER_COMPOSE) down --rmi all
	docker system prune -f

logs:
	$(DOCKER_COMPOSE) logs -f

shell:
	$(DOCKER_COMPOSE) exec $(APP_NAME) /bin/bash

test:
	$(DOCKER_COMPOSE) run --rm $(APP_NAME) python -m pytest

env:
	@if [ ! -f .env ]; then \
		echo "Creating .env file template..."; \
		echo "WEATHER_API_KEY=your_weather_api_key" > .env; \
		echo "GEO_API_KEY=your_geo_api_key" >> .env; \
		echo ".env file created. Please update with your actual API keys."; \
	else \
		echo ".env file already exists."; \
	fi