output "vm_ip" {
  description = "IP público fixo da VM afilibot"
  value       = azurerm_public_ip.afilibot.ip_address
}

output "ssh_command" {
  description = "Comando SSH para acessar a VM"
  value       = "ssh ubuntu@${azurerm_public_ip.afilibot.ip_address}"
}

output "app_url" {
  description = "URL da aplicação"
  value       = "http://${azurerm_public_ip.afilibot.ip_address}"
}
