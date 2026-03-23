.PHONY: help install install-flux install-test test test-unit lint format \
       build-orchestrator build-flux build-frontend build \
       deploy undeploy status logs-orchestrator logs-flux logs-frontend \
       dev dev-flux \
       frontend-install frontend-dev frontend-build frontend-preview frontend-check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Python ---

install: ## Install orchestrator dependencies
	pip install -r requirements.txt

install-flux: ## Install Flux server dependencies (requires CUDA)
	pip install -r requirements-flux.txt

install-test: ## Install test dependencies
	pip install -r requirements.txt
	pip install pytest pytest-asyncio httpx respx Pillow

test: ## Run all tests
	python -m pytest tests/ -v

test-unit: ## Run unit tests (no integration)
	python -m pytest tests/ -v -k "not e2e"

lint: ## Run linting
	python -m ruff check src/ tests/
	python -m ruff format --check src/ tests/

format: ## Auto-format code
	python -m ruff format src/ tests/

# --- Docker ---

REGISTRY ?= vecsmith
PLATFORM ?= linux/amd64

build-orchestrator: ## Build orchestrator Docker image
	docker build --platform $(PLATFORM) -f docker/Dockerfile.orchestrator -t $(REGISTRY)/orchestrator:latest .

build-flux: ## Build Flux server Docker image
	docker build --platform $(PLATFORM) -f docker/Dockerfile.flux-server -t $(REGISTRY)/flux-server:latest .

build-frontend: ## Build frontend Docker image
	docker build --platform $(PLATFORM) -f docker/Dockerfile.frontend -t $(REGISTRY)/frontend:latest .

build: build-orchestrator build-flux build-frontend ## Build all Docker images

# --- Kubernetes ---

NAMESPACE ?= vecsmith

deploy: ## Deploy to Kubernetes
	kubectl apply -f deploy/k8s/namespace.yaml
	kubectl apply -f deploy/k8s/flux-server/
	kubectl apply -f deploy/k8s/orchestrator/
	kubectl apply -f deploy/k8s/frontend/

undeploy: ## Remove from Kubernetes
	kubectl delete -f deploy/k8s/frontend/ --ignore-not-found
	kubectl delete -f deploy/k8s/orchestrator/ --ignore-not-found
	kubectl delete -f deploy/k8s/flux-server/ --ignore-not-found
	kubectl delete -f deploy/k8s/namespace.yaml --ignore-not-found

status: ## Show deployment status
	kubectl -n $(NAMESPACE) get pods,svc,ingress,pvc

logs-orchestrator: ## Tail orchestrator logs
	kubectl -n $(NAMESPACE) logs -f deployment/vecsmith-orchestrator

logs-flux: ## Tail Flux server logs
	kubectl -n $(NAMESPACE) logs -f deployment/vecsmith-flux-server

logs-frontend: ## Tail frontend logs
	kubectl -n $(NAMESPACE) logs -f deployment/vecsmith-frontend

# --- Development ---

dev: ## Run orchestrator locally
	VECSMITH_LLM_BASE_URL=http://localhost:8080/v1 \
	VECSMITH_FLUX_BASE_URL=http://localhost:8081 \
	python -m src.orchestrator.app

dev-flux: ## Run Flux server locally (requires NVIDIA GPU)
	python -m src.flux_server.server

# --- Frontend ---

FRONTEND_DIR = frontend

frontend-install: ## Install frontend dependencies
	cd $(FRONTEND_DIR) && npm install

frontend-dev: ## Run frontend dev server
	cd $(FRONTEND_DIR) && npm run dev -- --open

frontend-build: ## Build frontend for production
	cd $(FRONTEND_DIR) && npm run build

frontend-preview: ## Preview production build
	cd $(FRONTEND_DIR) && npm run preview -- --open

frontend-check: ## Type-check frontend
	cd $(FRONTEND_DIR) && npm run check
