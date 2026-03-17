terraform {
  required_version = ">= 1.9.0"
  required_providers {
    fly = {
      source  = "fly-apps/fly"
      version = "~> 0.0.23"
    }
  }
}

locals {
  backend_app  = "${var.app_name}-${var.environment}-api"
  frontend_app = "${var.app_name}-${var.environment}-web"
}

resource "fly_app" "backend" {
  name = local.backend_app
  org  = "personal"
}

resource "fly_app" "frontend" {
  name = local.frontend_app
  org  = "personal"
}

resource "fly_machine" "backend" {
  app    = fly_app.backend.name
  region = var.region
  name   = "${local.backend_app}-01"
  image  = "${var.backend_image}:${var.image_tag}"

  services = [{
    ports = [
      { port = 443, handlers = ["tls", "http"] },
      { port = 80, handlers = ["http"] },
    ]
    protocol      = "tcp"
    internal_port = 8000
  }]

  env = {
    APP_ENV      = var.environment
    LOG_LEVEL    = "INFO"
    DATABASE_URL = var.database_url
    SECRET_KEY   = var.secret_key
    CORS_ORIGINS = var.cors_origins
  }
}

resource "fly_machine" "frontend" {
  app    = fly_app.frontend.name
  region = var.region
  name   = "${local.frontend_app}-01"
  image  = "${var.frontend_image}:${var.image_tag}"

  services = [{
    ports = [
      { port = 443, handlers = ["tls", "http"] },
      { port = 80, handlers = ["http"] },
    ]
    protocol      = "tcp"
    internal_port = 8080
  }]
}
