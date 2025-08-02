# (c) 2018-2023 Tim Molteno (tim@elec.ac.nz)
build:
	DOCKER_BUILDKIT=1 docker compose build

install_uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh


test:
	docker compose -f compose.yml -f compose.test.yml up --build --abort-on-container-exit

test-client:
	uv run app/test_api.py

lint:
	uv run ruff check --fix app/

typecheck:
	uv run ty check app/
