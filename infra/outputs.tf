output "vm_ip" {
  description = "IP público fixo da VM afilibot"
  value       = google_compute_address.afilibot.address
}

output "ssh_command" {
  description = "Comando SSH para acessar a VM"
  value       = "ssh ubuntu@${google_compute_address.afilibot.address}"
}

output "app_url" {
  description = "URL da aplicação"
  value       = "http://${google_compute_address.afilibot.address}"
}
