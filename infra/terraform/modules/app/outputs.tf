output "backend_app_name" {
  description = "Deployed backend application name."
  value       = fly_app.backend.name
}

output "frontend_app_name" {
  description = "Deployed frontend application name."
  value       = fly_app.frontend.name
}

output "api_url" {
  description = "Public API base URL."
  value       = "https://${fly_app.backend.name}.fly.dev"
}

output "app_url" {
  description = "Public application URL."
  value       = "https://${fly_app.frontend.name}.fly.dev"
}

output "deployed_image_tag" {
  description = "Image tag currently deployed -- record this for rollback."
  value       = var.image_tag
}
