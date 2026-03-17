# Interface for one deployed environment of the application.
#
# Deliberately provider-neutral in shape: the same inputs describe the app on
# Fly.io today and on a self-hosted Docker/Nomad/Compose target later, so
# migrating hosts means swapping this module's implementation, not the
# environment definitions that consume it.

variable "environment" {
  description = "Environment name (staging, production)."
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be one of: staging, production."
  }
}

variable "app_name" {
  description = "Base name for the deployed applications."
  type        = string
}

variable "region" {
  description = "Primary region for the app and its database."
  type        = string
}

variable "image_tag" {
  description = "Container image tag to deploy (12-char commit SHA)."
  type        = string
}

variable "backend_image" {
  description = "Fully-qualified backend image repository."
  type        = string
}

variable "frontend_image" {
  description = "Fully-qualified frontend image repository."
  type        = string
}

variable "database_url" {
  description = "Async SQLAlchemy DSN for the environment's Postgres."
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "JWT signing key for the environment."
  type        = string
  sensitive   = true
}

variable "cors_origins" {
  description = "Comma-separated allowed origins. Never '*' outside local."
  type        = string
  validation {
    condition     = !can(regex("\\*", var.cors_origins))
    error_message = "Wildcard CORS origins are not permitted in deployed environments."
  }
}

variable "min_machines" {
  description = "Minimum running instances of the backend."
  type        = number
  default     = 1
}
