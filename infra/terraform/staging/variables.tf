variable "fly_api_token" {
  description = "Fly.io API token. Supplied via TF_VAR_fly_api_token from CI secrets."
  type        = string
  sensitive   = true
}

variable "app_name" {
  description = "Base application name."
  type        = string
  default     = "finance-tracker"
}

variable "region" {
  description = "Deployment region."
  type        = string
  default     = "lhr"
}

variable "image_tag" {
  description = "Container image tag to deploy."
  type        = string
}

variable "backend_image" {
  description = "Backend image repository."
  type        = string
}

variable "frontend_image" {
  description = "Frontend image repository."
  type        = string
}

variable "database_url" {
  description = "Postgres DSN for this environment."
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "JWT signing key for this environment."
  type        = string
  sensitive   = true
}

variable "cors_origins" {
  description = "Comma-separated allowed origins."
  type        = string
}

variable "min_machines" {
  description = "Minimum backend instances."
  type        = number
  default     = 1
}
