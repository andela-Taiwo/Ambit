output "api_url" {
  description = "Public API base URL for staging."
  value       = module.app.api_url
}

output "app_url" {
  description = "Public application URL for staging."
  value       = module.app.app_url
}

output "deployed_image_tag" {
  description = "Image tag deployed to staging -- record for rollback."
  value       = module.app.deployed_image_tag
}
