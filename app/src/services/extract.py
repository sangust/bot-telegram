import httpx
from ..infrabackend.config import SHOPIFY_URLS, NUVEMSHOP_URLS
from ..infrabackend.schemas import ProductSchema
from ..infrabackend.database import LocalDatabase
from ..infrabackend.repository import LocalRepository
from bs4 import BeautifulSoup
import re
from datetime import date


class extract:
    def __init__(self, db=LocalDatabase, query=LocalRepository):
        self.db = query(db=db())

    def shopify(self, SHOPIFY_URLS: dict = SHOPIFY_URLS):
        for brand, url in SHOPIFY_URLS.items():
            try:
                with httpx.Client(timeout=10) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    data: dict = response.json()

                    for item in data.get("products", []):
                        item: dict
                        for variant in item.get("variants", []):
                            try:
                                link = url.replace(
                                    "/products.json?limit=250",
                                    f"/products/{item['handle']}"
                                )

                                images = item.get("images") or []
                                image = images[0].get("src") if images else None

                                discount_price = float(variant.get("price"))
                                raw_compare = variant.get("compare_at_price")
                                compare_at_price = float(raw_compare) if raw_compare else None

                                if discount_price is None:
                                    raise ValueError("invalid price")

                                full_price = compare_at_price if compare_at_price and compare_at_price > discount_price else discount_price

                                product = ProductSchema(
                                    brand=brand,
                                    name=item["title"],
                                    clothing_id=int(variant["id"]),
                                    discount_price=discount_price,
                                    full_price=full_price,
                                    available=variant["available"],
                                    size=variant["title"],
                                    link=link,
                                    image=image,
                                    sent_at=date.today()
                                )

                                try:
                                    self.db.add(product=product)
                                    self.db.commit()
                                except Exception:
                                    try:
                                        self.db.update(product=product)
                                        self.db.commit()
                                    except Exception as e:
                                        print(f"[DB ERROR] Product failed | Brand={brand} | Name={item.get('title')} | Error={e}")
                                        self.db.session.rollback()

                            except Exception as e:
                                print(
                                    f"[VALIDATION] Product ignored | Brand={brand} | "
                                    f"Name={item.get('title')} | Error={e}"
                                )

            except Exception as e:
                print(f"[SCRAPE ERROR] Brand={brand} | Error={e}")

    def nuvemshop(self, NUVEMSHOP_URLS=NUVEMSHOP_URLS):
        """
        Extract products from Nuvemshop stores via scraping
        NUVEMSHOP_URLS must be: {"brand": "https://store.com"}
        """

        for brand, base_url in NUVEMSHOP_URLS.items():
            try:
                base_url = base_url.rstrip('/')
                products_url = f"{base_url}/produtos/"

                print(f"[INFO] Starting extraction for {brand}")

                with httpx.Client(timeout=10, follow_redirects=True) as client:
                    page = 1
                    has_more = True
                    processed_products = 0

                    while has_more:
                        try:
                            url = f"{products_url}?page={page}"
                            response = client.get(url)
                            response.raise_for_status()
                            soup = BeautifulSoup(response.text, 'html.parser')

                            product_items = soup.select(
                                '.item-product, .product-item, [itemtype*="Product"]'
                            )

                            if not product_items:
                                all_links = soup.select('a[href*="/produtos/"]')
                                product_links = []
                                seen_slugs = set()

                                for link_tag in all_links:
                                    href = link_tag.get('href', '')
                                    match = re.search(r'/produtos/([a-z0-9\-]+)/?$', href)
                                    if match:
                                        slug = match.group(1)
                                        if slug not in seen_slugs and slug != '':
                                            seen_slugs.add(slug)
                                            product_links.append((slug, href))

                                if not product_links:
                                    print(f"[INFO] No products found on page {page}")
                                    has_more = False
                                    break
                            else:
                                product_links = []
                                for item in product_items:
                                    link_tag = item.select_one('a[href*="/produtos/"]')
                                    if link_tag:
                                        href = link_tag.get('href', '')
                                        match = re.search(r'/produtos/([a-z0-9\-]+)/?$', href)
                                        if match:
                                            product_links.append((match.group(1), href))

                            for slug, href in product_links:
                                try:
                                    product_url = href if href.startswith('http') else f"{base_url}{href}"

                                    print(f"[INFO] Processing product: {slug}")

                                    prod_response = client.get(product_url)
                                    prod_response.raise_for_status()
                                    prod_soup = BeautifulSoup(prod_response.text, 'html.parser')

                                    name_element = prod_soup.select_one(
                                        'h1.product-name, h1[itemprop="name"], .product-title h1, h1'
                                    )
                                    name = (
                                        name_element.get_text(strip=True)
                                        if name_element
                                        else slug.replace('-', ' ').title()
                                    )

                                    discount_price = None

                                    price_selectors = [
                                        'span.price-amount',
                                        'span[itemprop="price"]',
                                        '.product-price span',
                                        '#price_display',
                                        '.js-price-display',
                                    ]

                                    for selector in price_selectors:
                                        price_element = prod_soup.select_one(selector)
                                        if price_element:
                                            price_text = price_element.get_text(strip=True)
                                            price_clean = re.sub(r'[^\d,]', '', price_text)

                                            if price_clean:
                                                try:
                                                    discount_price = float(price_clean.replace(',', '.'))
                                                    break
                                                except ValueError:
                                                    continue

                                    if discount_price is None:
                                        print(f"[WARN] Price not found for {slug}, skipping...")
                                        continue

                                    full_price = discount_price

                                    compare_element = prod_soup.select_one(
                                        '.price-compare, .compare-at-price, del, s'
                                    )
                                    if compare_element:
                                        compare_text = compare_element.get_text(strip=True)
                                        compare_clean = re.sub(r'[^\d,]', '', compare_text)

                                        if compare_clean:
                                            try:
                                                compare_at_price = float(compare_clean.replace(',', '.'))
                                                if compare_at_price > discount_price:
                                                    full_price = compare_at_price
                                            except ValueError:
                                                pass

                                    image = None
                                    img_element = prod_soup.select_one(
                                        '.product-image img, img[itemprop="image"], .js-product-slide-img'
                                    )
                                    if img_element:
                                        image = img_element.get('data-src') or img_element.get('src')
                                        if image and image.startswith('//'):
                                            image = 'https:' + image

                                    variants = []

                                    variant_select = prod_soup.select_one(
                                        'select.js-variation-option, select[name*="variation"]'
                                    )
                                    if variant_select:
                                        for option in variant_select.find_all('option'):
                                            text = option.get_text(strip=True)
                                            if text and text.lower() not in ['selecione', 'escolha', '']:
                                                available = not option.get('disabled', False)
                                                variants.append({
                                                    'size': text,
                                                    'available': available
                                                })

                                    if not variants:
                                        variants.append({'size': 'Unique', 'available': True})

                                    for variant in variants:
                                        try:
                                            variant_hash = hash(f"{brand}-{slug}-{variant['size']}") % (10 ** 10)

                                            product = ProductSchema(
                                                brand=brand,
                                                name=name,
                                                clothing_id=variant_hash,
                                                discount_price=discount_price,
                                                full_price=full_price,
                                                available=variant['available'],
                                                size=variant['size'],
                                                link=product_url,
                                                image=image,
                                                sent_at=date.today()
                                            )

                                            try:
                                                self.db.update(product=product)
                                                self.db.commit()
                                            except Exception:
                                                try:
                                                    self.db.add(product=product)
                                                    self.db.commit()
                                                except Exception as e:
                                                    print(f"[DB ERROR] Product failed | Brand={brand} | Name={name} | Error={e}")
                                                    self.db.session.rollback()

                                            processed_products += 1

                                        except Exception as e:
                                            print(f"[VARIANT ERROR] Brand={brand} | Product={name} | Error={e}")

                                except Exception as e:
                                    print(f"[PRODUCT ERROR] Brand={brand} | Slug={slug} | Error={e}")

                            page += 1
                            next_link = soup.select_one('a.next, a[rel="next"], .pagination-next')
                            if not next_link or page > 20:
                                has_more = False

                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                has_more = False
                            else:
                                raise

                    print(f"[INFO] Total processed for {brand}: {processed_products}")

            except Exception as e:
                print(f"[SCRAPE ERROR] Brand={brand} | Error={e}")

        print("[SUCCESS] Database commit completed")