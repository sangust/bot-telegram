terraform{
    required_providers {
        google = {
            source = "hashicorp/google"
            version = ">= 5.0"
        }
    }
}

provider "google"{
    project = var.project_id
    region = var.region
    zone = var.zone
    credentials = file("credentials.json")
}

resource "google_compute_instance" "afilibot"{
    name = "afilibot"
    machine_type = "e2-micro"
    zone = var.zone
    tags = ["web-server"]

    boot_disk{
        initialize_params{
            image = "debian-cloud/debian-12"
            size = 20
        }
    }

    network_interface {
        network = "default"
        access_config {}  
    }

    metadata_startup_script = file("startup.sh")
    
}

resource "google_compute_firewall" "allow_8000"{
    name = "allow8000"
    network = "default"
    allow {
        protocol = "tcp"
        ports = ["80", "8000"]
    }

    source_ranges = ["0.0.0.0/0"]
    target_tags = ["web-server"]
}