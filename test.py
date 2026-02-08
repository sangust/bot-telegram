from src.garimpo.services.extract import extract
from src.garimpo.infra.repository import CloudProductRepository

if __name__ == "__main__":
    extracts = extract()
    extracts.shopify()
    extracts.nuvemshop()

    gcp = CloudProductRepository()
    gcp.sync_local_to_cloud()
    