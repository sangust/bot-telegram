terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.region
  zone    = var.zone
}

locals {
  common_labels = {
    projeto = "afilibot"
    env     = "production"
  }
}

resource "google_compute_network" "afilibot" {
  name                    = "afilibot-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "afilibot" {
  name          = "afilibot-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.afilibot.id
}

resource "google_compute_address" "afilibot" {
  name   = "afilibot-ip"
  region = var.region
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "afilibot-allow-ssh"
  network = google_compute_network.afilibot.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["afilibot"]
}

resource "google_compute_firewall" "allow_http" {
  name    = "afilibot-allow-http"
  network = google_compute_network.afilibot.name

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["afilibot"]
}

resource "google_compute_firewall" "allow_https" {
  name    = "afilibot-allow-https"
  network = google_compute_network.afilibot.name

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["afilibot"]
}

resource "google_compute_instance" "afilibot" {
  name         = "afilibot"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["afilibot"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
      size  = 30
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.afilibot.id

    access_config {
      nat_ip = google_compute_address.afilibot.address
    }
  }

  metadata = {
    ssh-keys = "ubuntu:${var.ssh_public_key}"
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    database_url               = var.database_url
    secret_key                 = var.secret_key
    google_client_id           = var.google_client_id
    google_client_secret       = var.google_client_secret
    google_redirect_uri        = var.google_redirect_uri
    mercadopago_access_token   = var.mercadopago_access_token
    mercadopago_webhook_secret = var.mercadopago_webhook_secret
    base_url                   = var.base_url
    bot_token_1                = var.bot_token_1
    bot_token_2                = var.bot_token_2
    bot_token_3                = var.bot_token_3
    dockerhub_username         = var.dockerhub_username
    dockerhub_token            = var.dockerhub_token
    db_password                = var.db_password
    worker_count               = var.worker_count
  })

  labels = local.common_labels
}
