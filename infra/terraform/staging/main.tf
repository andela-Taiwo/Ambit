terraform {
  required_version = ">= 1.9.0"

  required_providers {
    fly = {
      source  = "fly-apps/fly"
      version = "~> 0.0.23"
    }
  }

  # Remote state keeps the deploy pipeline stateless and lockable.
  # Configure with: terraform init -backend-config=backend.hcl
  backend "s3" {}
}

provider "fly" {
  fly_api_token = var.fly_api_token
}

module "app" {
  source = "../modules/app"

  environment    = "staging"
  app_name       = var.app_name
  region         = var.region
  image_tag      = var.image_tag
  backend_image  = var.backend_image
  frontend_image = var.frontend_image
  database_url   = var.database_url
  secret_key     = var.secret_key
  cors_origins   = var.cors_origins
  min_machines   = var.min_machines
}
