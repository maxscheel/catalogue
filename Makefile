# (c) 2018-2023 Tim Molteno (tim@elec.ac.nz)
build:
	DOCKER_BUILDKIT=1 docker compose build
test:
	docker compose up --build

test-client:
	python3 app/test_api.py

lint:
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# FastAPI V2 variants
fastapi-minimal:
	@echo "Creating minimal FastAPI v2 (core functionality only)..."
	@cp app/fastapi_v2.py app/fastapi_v2_backup.py
	@sed '/# OPTIONAL IMPORTS/,/# PROJECT IMPORTS/c\# =============================================================================\n# PROJECT IMPORTS - Core dependencies\n# =============================================================================' app/fastapi_v2.py > app/fastapi_v2_minimal.py
	@sed -i '/# OPTIONAL PYDANTIC MODELS/,/# GLOBAL STATE/d' app/fastapi_v2_minimal.py
	@sed -i '/# OPTIONAL GLOBAL STATE/,/# FASTAPI APPLICATION SETUP/d' app/fastapi_v2_minimal.py
	@sed -i '/# OPTIONAL MIDDLEWARE/,/# STARTUP EVENTS/d' app/fastapi_v2_minimal.py
	@sed -i '/# OPTIONAL API ENDPOINTS/,/# OPTIONAL FEATURES/d' app/fastapi_v2_minimal.py
	@sed -i '/# OPTIONAL FEATURES/,$$d' app/fastapi_v2_minimal.py
	@echo "Minimal version created as app/fastapi_v2_minimal.py"

fastapi-full:
	@echo "Full FastAPI v2 with all features (current version)"
	@echo "File: app/fastapi_v2.py"

fastapi-clean:
	@echo "Removing generated FastAPI variants..."
	@rm -f app/fastapi_v2_minimal.py app/fastapi_v2_backup.py

fastapi-analyze:
	@echo "=== FastAPI V2 Code Analysis ==="
	@echo "Lines of code in full version:"
	@wc -l app/fastapi_v2.py
	@if [ -f app/fastapi_v2_minimal.py ]; then \
		echo "Lines of code in minimal version:"; \
		wc -l app/fastapi_v2_minimal.py; \
		echo "Reduction:"; \
		python3 -c "full=$$(wc -l < app/fastapi_v2.py); minimal=$$(wc -l < app/fastapi_v2_minimal.py); print(f'{full-minimal} lines removed ({(full-minimal)/full*100:.1f}% reduction)')"; \
	fi
	@echo ""
	@echo "=== Dead code candidates ==="
	@echo "Optional imports (can be removed):"
	@grep -n "# Only needed for" app/fastapi_v2.py || echo "None found"
	@echo ""
	@echo "Optional sections (can be removed):"
	@grep -n "# OPTIONAL" app/fastapi_v2.py | cut -d: -f2
