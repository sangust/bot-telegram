terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "afilibot"
    storage_account_name = "afilibottfstate"
    container_name       = "tfstate"
    key                  = "prod.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "afilibot" {
  name     = "afilibot"
  location = var.location

  tags = {
    projeto = "afilibot"
    env     = "production"
  }
}

resource "azurerm_public_ip" "afilibot" {
  name                = "afilibot-ip"
  location            = var.location
  resource_group_name = azurerm_resource_group.afilibot.name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = { projeto = "afilibot" }
}

resource "azurerm_virtual_network" "afilibot" {
  name                = "afilibot-vnet"
  location            = var.location
  resource_group_name = azurerm_resource_group.afilibot.name
  address_space       = ["10.0.0.0/16"]
}

resource "azurerm_subnet" "afilibot" {
  name                 = "afilibot-subnet"
  resource_group_name  = azurerm_resource_group.afilibot.name
  virtual_network_name = azurerm_virtual_network.afilibot.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_network_security_group" "afilibot" {
  name                = "afilibot-nsg"
  location            = var.location
  resource_group_name = azurerm_resource_group.afilibot.name

  security_rule {
    name                       = "SSH"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "HTTP"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "HTTPS"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "afilibot" {
  name                = "afilibot-nic"
  location            = var.location
  resource_group_name = azurerm_resource_group.afilibot.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.afilibot.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.afilibot.id
  }
}

resource "azurerm_network_interface_security_group_association" "afilibot" {
  network_interface_id      = azurerm_network_interface.afilibot.id
  network_security_group_id = azurerm_network_security_group.afilibot.id
}

resource "azurerm_linux_virtual_machine" "afilibot" {
  name                = "afilibot"
  location            = var.location
  resource_group_name = azurerm_resource_group.afilibot.name
  size                = var.vm_size
  admin_username      = "ubuntu"

  network_interface_ids = [
    azurerm_network_interface.afilibot.id
  ]

  admin_ssh_key {
    username   = "ubuntu"
    public_key = var.ssh_public_key
  }

  os_disk {
    name                 = "afilibot-osdisk"
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 30
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  # Injeta as variáveis no startup.sh via templatefile
  custom_data = base64encode(templatefile("${path.module}/startup.sh", {
    database_url              = var.database_url
    secret_key                = var.secret_key
    google_client_id          = var.google_client_id
    google_client_secret      = var.google_client_secret
    google_redirect_uri       = var.google_redirect_uri
    mercadopago_access_token  = var.mercadopago_access_token
    mercadopago_webhook_secret = var.mercadopago_webhook_secret
    base_url                  = var.base_url
    bot_token_1               = var.bot_token_1
    bot_token_2               = var.bot_token_2
    bot_token_3               = var.bot_token_3
    dockerhub_username        = var.dockerhub_username
    dockerhub_token           = var.dockerhub_token
    db_password               = var.db_password
    worker_count              = var.worker_count
  }))

  tags = {
    projeto = "afilibot"
    env     = "production"
  }
}
