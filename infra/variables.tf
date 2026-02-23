variable "location" {
  description = "Região do Azure onde os recursos serão criados"
  type        = string
  default     = "Brazil South"
}

variable "ssh_public_key" {
  description = "Chave pública SSH para acesso à VM"
  type        = string
  sensitive   = true
  # GitHub Secret: TF_VAR_ssh_public_key
}

variable "db_password" {
  description = "Senha do postgres rodando no Docker da VM"
  type        = string
  sensitive   = true
  # GitHub Secret: TF_VAR_db_password
}

variable "dockerhub_username" {
  description = "Username do Docker Hub"
  type        = string
  # GitHub Secret: TF_VAR_dockerhub_username
}

variable "dockerhub_token" {
  description = "Token do Docker Hub"
  type        = string
  sensitive   = true
  # GitHub Secret: TF_VAR_dockerhub_token
}

# ── App ────────────────────────────────────────────────────────────────────────
variable "database_url" {
  description = "Connection string do PostgreSQL"
  type        = string
  sensitive   = true
  # GitHub Secret: TF_VAR_database_url
}

variable "secret_key" {
  description = "SECRET_KEY do SessionMiddleware"
  type        = string
  sensitive   = true
  # GitHub Secret: TF_VAR_secret_key
}

variable "google_client_id" {
  type      = string
  sensitive = true
  # GitHub Secret: TF_VAR_google_client_id
}

variable "google_client_secret" {
  type      = string
  sensitive = true
  # GitHub Secret: TF_VAR_google_client_secret
}

variable "google_redirect_uri" {
  type = string
  # GitHub Secret: TF_VAR_google_redirect_uri
}

variable "abacatepay_api_key" {
  type      = string
  sensitive = true
  # GitHub Secret: TF_VAR_abacatepay_api_key
}

variable "abacatepay_api_url" {
  type    = string
  default = "https://api.abacatepay.com/v1"
}

variable "abacatepay_webhook_secret" {
  type      = string
  sensitive = true
  # GitHub Secret: TF_VAR_abacatepay_webhook_secret
}

variable "base_url" {
  description = "URL pública da aplicação (ex: http://IP_DA_VM)"
  type        = string
  # GitHub Secret: TF_VAR_base_url
}

variable "bot_token_1" {
  type      = string
  sensitive = true
  # GitHub Secret: TF_VAR_bot_token_1
}

variable "bot_token_2" {
  type      = string
  sensitive = true
  # GitHub Secret: TF_VAR_bot_token_2
}

variable "bot_token_3" {
  type      = string
  sensitive = true
  # GitHub Secret: TF_VAR_bot_token_3
}
