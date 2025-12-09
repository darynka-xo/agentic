.PHONY: help build run stop restart logs clean test docker-build docker-run docker-stop k8s-deploy k8s-delete k8s-logs

# Variables
IMAGE_NAME=llm-smeta-pir
IMAGE_TAG=latest
CONTAINER_NAME=llm-smeta-pir
PORT=8010
NAMESPACE=llm-smeta-pir

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# Docker Commands
docker-build: ## Build Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

docker-run: ## Run Docker container
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):$(PORT) \
		--env-file .env \
		$(IMAGE_NAME):$(IMAGE_TAG)

docker-stop: ## Stop and remove Docker container
	docker stop $(CONTAINER_NAME) || true
	docker rm $(CONTAINER_NAME) || true

docker-restart: docker-stop docker-run ## Restart Docker container

docker-logs: ## View Docker container logs
	docker logs -f $(CONTAINER_NAME)

docker-shell: ## Open shell in Docker container
	docker exec -it $(CONTAINER_NAME) bash

# Docker Compose Commands
compose-up: ## Start services with docker-compose
	docker-compose up -d

compose-down: ## Stop services with docker-compose
	docker-compose down

compose-logs: ## View docker-compose logs
	docker-compose logs -f

compose-restart: ## Restart docker-compose services
	docker-compose restart

# Kubernetes Commands
k8s-create-namespace: ## Create Kubernetes namespace
	kubectl create namespace $(NAMESPACE) || true

k8s-deploy: ## Deploy to Kubernetes
	kubectl apply -f k8s-deployment.yaml -n $(NAMESPACE)
	kubectl apply -f k8s-service.yaml -n $(NAMESPACE)

k8s-delete: ## Delete from Kubernetes
	kubectl delete -f k8s-service.yaml -n $(NAMESPACE) || true
	kubectl delete -f k8s-deployment.yaml -n $(NAMESPACE) || true

k8s-logs: ## View Kubernetes logs
	kubectl logs -l app=llm-smeta-pir -n $(NAMESPACE) --tail=100 -f

k8s-pods: ## List Kubernetes pods
	kubectl get pods -n $(NAMESPACE)

k8s-services: ## List Kubernetes services
	kubectl get svc -n $(NAMESPACE)

k8s-describe: ## Describe Kubernetes deployment
	kubectl describe deployment/llm-smeta-pir -n $(NAMESPACE)

k8s-restart: ## Restart Kubernetes deployment
	kubectl rollout restart deployment/llm-smeta-pir -n $(NAMESPACE)

k8s-status: ## Check rollout status
	kubectl rollout status deployment/llm-smeta-pir -n $(NAMESPACE)

k8s-port-forward: ## Port forward to local machine
	kubectl port-forward svc/llm-smeta-pir $(PORT):$(PORT) -n $(NAMESPACE)

# Development Commands
dev-install: ## Install dependencies
	pip install -r requirements.txt

dev-run: ## Run development server
	python server.py

dev-test: ## Run tests
	python -m pytest tests/ -v

# Cleanup Commands
clean: ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	rm -rf .pytest_cache

clean-docker: docker-stop ## Clean Docker resources
	docker rmi $(IMAGE_NAME):$(IMAGE_TAG) || true

# Testing Commands
test-api: ## Test API locally
	curl http://localhost:$(PORT)/docs

test-health: ## Test health endpoint
	curl -f http://localhost:$(PORT)/docs || echo "Service is not healthy"

# All-in-one Commands
build-and-run: docker-build docker-run ## Build and run Docker container

deploy-all: k8s-create-namespace docker-build k8s-deploy ## Build and deploy to Kubernetes

