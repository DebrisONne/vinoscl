from django.http import HttpResponse
from bs4 import BeautifulSoup
from .models import Product, Store, ProductStore, ProductPrice 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from django.shortcuts import render, get_object_or_404
from tempfile import NamedTemporaryFile
from urllib.request import urlopen
from django.core.files import File
import time, re, uuid, locale, spacy, tempfile
from selenium.common.exceptions import NoSuchElementException
from urllib.parse import urljoin, urlparse
import pprint
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from django.db.models import Q, Count
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q
from selenium.webdriver.chrome.options import Options




def index(request):
    products_with_multiple_prices = ProductPrice.objects.values('product').annotate(price_count=Count('product')).filter(price_count__gt=1).values_list('product', flat=True)
    products = Product.objects.filter(id__in=products_with_multiple_prices)[:20]

    return render(request, 'index.html', {'products': products})

def product_detail(request, product_id):
    product = Product.objects.get(pk=product_id)
    product_prices = ProductPrice.objects.filter(product = product)
    locale.setlocale(locale.LC_ALL, 'es_CL.UTF-8')
    for price in product_prices:
        price.price = locale.currency(price.price, grouping=True)
    
    return render(request, 'product_detail.html', {'product': product, 'product_prices': product_prices})

def clean_database(request):
    Product.objects.all().delete()
    ProductStore.objects.all().delete()
    ProductPrice.objects.all().delete()

    return HttpResponse("Base de datos limpiada correctamente.")

def clean_numbers(texto):
    return re.sub(r'\D', '', texto)

def check_product_existence(data):
    name = data.get('product_name')
    # image_url = data.get('image_url')

    # similar_products = Product.objects.all()

    # similar_products = Product.objects.filter(
    #     Q(name__icontains=name) | Q(name__iregex=r"\b{}\b".format(name))
    # )

    keywords = name.split()

    queries = [Q(name__icontains=keyword) for keyword in keywords]

    combined_query = queries.pop()
    for query in queries:
        combined_query |= query

    similar_products = Product.objects.filter(combined_query)

    for product in similar_products:
        print('comparando', name, 'con', product.name)
        if similar_names(name, product.name):
            print('Coincidencia encontrada, ignorando producto...')
            return product

    print('Sin coincidencias, guardando producto...')
    return None 


def similar_names(name1, name2):
    name1 = name1.lower()
    name2 = name2.lower()

    name1 = name1.strip()
    name2 = name2.strip()

    name1 = re.sub(r'[^\w\s]', '', name1)
    name2 = re.sub(r'[^\w\s]', '', name2)

    nlp = spacy.load("es_core_news_sm")
    name_1 = nlp(name1)
    name_2 = nlp(name2)

    similarity = name_1.similarity(name_2)

    if(similarity >= 0.8):
        return True
    else :
        return False


def similar_descriptions(desc1, desc2):
    return desc1[:100] == desc2[:100]


def similar_images(img1, img2):
    return img1 == img2


def update_products(data):
    scrape_vinoteca() 
    scrape_ewine()
    scrape_mundo_vino()    
    
    return HttpResponse("Done.")


def save_product(data):
    existing_product = check_product_existence(data)
    product_price = data.get('product_price')
    store = data.get('store')
    product_name = data.get('product_name')
    forbidden_words = ['maleta', 'caja', 'juego', 'estuche', 'regalo','pack']

    for word in forbidden_words:
        if word in product_name.lower():
            print(f'Pack detectado, se omite producto.')
            return False

    if not existing_product:
        product_url = data.get('product_url')
        image_url = data.get('image_url')
        current_page = data.get('current_page')
        product_availability = data.get('product_availability')

        product = Product(name=product_name)
        product.save()

        product_store = ProductStore(product=product, store=store, url=product_url)
        product_store.save()    

        if image_url:
            img_temp = NamedTemporaryFile(delete=True)
            img_temp.write(urlopen(image_url).read())
            img_temp.flush()
            unique_filename = f"{uuid.uuid4()}.jpg"
            product.image.save(unique_filename, File(img_temp))
            
        if product_price:
            productPrice = ProductPrice(product = product, price = clean_numbers(product_price), store = store)          
            productPrice.save()

        print('Página:', current_page)
        print('Producto registrado:', product.name)
        if product_price:
            print('Precio:', product_price)
        print('*------------------------------------------------------------------*')

        return True
    else:
        if product_price:
            product_price_instance = ProductPrice.objects.filter(product=existing_product, store=store).first()
            if product_price_instance:
                product_price_instance.price = clean_numbers(product_price)
                product_price_instance.save()
                print('El precio del producto existente ha sido actualizado:', product_price)
            else:
                product_price_instance = ProductPrice(product=existing_product, price=clean_numbers(product_price), store=store)
                product_price_instance.save()
                print('precio entidad nueva = ' + str(product_price_instance.price))
            return True
        else:
            print('El producto ya existe en la base de datos, pero no se proporcionó un precio. No se guardó el precio.')
            return False


def scrape_vinoteca():
    print('******* SCRAPING VINOTECA *******')
    store = Store.objects.get(pk=7)
    url = "https://www.lavinoteca.cl/home?O=OrderByNameASC&PS=64"
    # url = "https://www.lavinoteca.cl/Requingua%20Toro%20de%20Piedra%20Espumante%20Brut"
    # s = Service(r"F:/Coding/freelnce/vinoscl/chromedriver-win64/chromedriver.exe")
    # driver = webdriver.Chrome(service=s)
    options = Options()
    options.headless = True  # Ejecutar en modo headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    driver.get(url)
    time.sleep(5)

    while True:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        product_elements = soup.find_all('div', class_='item')

        for product_element in product_elements:
            product_name_element = product_element.find('h3', class_='name')

            if product_name_element:
                product_name = product_name_element.find('a').text.strip()
                product_url = product_name_element.find('a')['href']
                price_span = product_element.find('span', class_='current-price-discount')
                product_availability = product_element.find('div', class_='producto-agotado')            
                image_element = product_element.find('img')
                image_url = image_element['src'] if image_element else None 

                if not product_availability:
                    if price_span:
                        price = price_span.text.strip()
                    else:
                        price_span = product_element.find('span', class_='current-price')
                        price = price_span.text.strip()
                else:
                    price = None

                active_page_element = driver.find_element(By.CSS_SELECTOR, 'div.pager.bottom li.pgCurrent')
                current_page = int(active_page_element.text)

                product_data = {
                    'product_url': product_url,
                    'image_url': image_url,
                    'product_name': product_name,
                    'product_price': price,
                    'store': store,
                    'current_page': current_page,
                    'product_availability': product_availability
                }

                save_product(product_data)

        try:
            pager_bottom = driver.find_element(By.XPATH, '//div[starts-with(@id, "PagerBottom_")]')
            next_button = pager_bottom.find_element(By.CLASS_NAME, 'next')
            if 'pgEmpty' in next_button.get_attribute('class'):
                break
            next_button.click()
            time.sleep(5) 
        except:
            break  

    driver.quit()
    print("******* TIENDA VINOTECA FINALIZADA *******")
    return True


def scrape_ewine():
    print('******* SCRAPING EWINE *******')
    store = Store.objects.get(pk=8)
    url = "https://ewine.cl/vinos-12?q=Filtros-Botellas+individuales"
    # url = 'https://ewine.cl/vinos-12?q=Filtros-Botellas+individuales&order=product.name.asc'
    # url = "https://ewine.cl/vinos-12?q=Filtros-Botellas+individuales&order=product.name.asc&page=10"
    # s = Service(r"F:/Coding/freelnce/vinoscl/chromedriver-win64/chromedriver.exe")
    # driver = webdriver.Chrome(service=s)
    options = Options()
    options.headless = True  # Ejecutar en modo headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    driver.get(url)
    time.sleep(5)



    while True:
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        try:
            close_button = driver.find_element(By.CLASS_NAME, '_close-icon') 
            close_button.click()
        except:
            print('Modal no existe >>> continuando')

        try:
            age_modal = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "ets_av_content_popup")))
            yes_button = age_modal.find_element(By.ID, "ets_av_their_self")
            
            if yes_button.is_displayed() and yes_button.is_enabled():
                actions = ActionChains(driver)
                actions.move_to_element(yes_button).perform()
                
                yes_button.click()
            else:
                print("El botón 'Sí' no está disponible para ser clickeado")
        except Exception as e:
            print(f"No se pudo encontrar o hacer clic en el botón 'Sí' en el modal de verificación de edad: {str(e)}")


        product_elements = soup.find_all('article', class_='product-miniature')

        for product_element in product_elements:
            product_name_element = product_element.find('h3', class_='product-title')

            if product_name_element:
                product_name = product_name_element.find('a').text.strip()
                product_url = product_name_element.find('a')['href']
                price_span = product_element.find('span', class_='product-price')
                # product_availability = product_element.find('div', class_='producto-agotado')            
                image_element = product_element.find('img', class_='product-thumbnail-first')
                image_url = image_element['data-src'] if image_element else None 
                
                if price_span:
                    price = price_span.text.strip()
                else:
                    price_span = product_element.find('span', class_='current-price')
                    price = price_span.text.strip()
               
                active_page_element = driver.find_element(By.CSS_SELECTOR, 'div.pagination-wrapper li.current')
                current_page = int(active_page_element.text)

                product_data = {
                    'product_url': product_url,
                    'image_url': image_url,
                    'product_name': product_name,
                    'product_price': price,
                    'store': store,
                    'current_page': current_page
                }

                save_product(product_data)

        try:
            pager_bottom = driver.find_element(By.CLASS_NAME, 'pagination')
            next_button = pager_bottom.find_element(By.CLASS_NAME, 'next')
            if 'disabled' in next_button.get_attribute('class'):
                break
            next_button.click()
            time.sleep(5) 
        except NoSuchElementException:
            print("El botón 'Next' no se encontró en la página actual")
            return False
        except Exception as e:
            print(f"Error: {str(e)}")
            return False

    driver.quit()
    print("******* TIENDA EWINE FINALIZADA *******")
    return True
    

def scrape_mundo_vino():
    store = Store.objects.get(pk=9)
    url = "https://elmundodelvino.cl/collections/vinos?sort_by=title-ascending"
    # s = Service(r"F:/Coding/freelnce/vinoscl/chromedriver-win64/chromedriver.exe")
    # driver = webdriver.Chrome(service=s)
    options = Options()
    options.headless = True  # Ejecutar en modo headless
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    driver.get(url)
    time.sleep(5)

    img_temp = tempfile.NamedTemporaryFile(delete=True)
    while True:
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        product_container = soup.find('div', class_='new-grid product-grid collection-grid')
        if not product_container:
            print("No se encontró el contenedor de productos")
            break
        product_elements = product_container.find_all('div', class_='grid-item grid-product')

        for product_element in product_elements:
            product_name_element = product_element.find('div', class_='grid-product__title')

            if product_name_element:
                product_name = product_name_element.text.strip()
                product_url = product_element.find('a',  class_='grid-item__link')['href']
                price_span = product_element.find('span', class_='grid-product__price--current')
                # product_availability = product_element.find('div', class_='producto-agotado')            
                image_element = product_element.find('img', class_='grid__image-contain')
                srcset = image_element.get('srcset')
                if srcset:
                    urls = srcset.split(',')
                    best_quality_url = urls[-1].strip().split(' ')[0]
                    if best_quality_url.startswith('//'):
                        best_quality_url = 'https:' + best_quality_url
                    if best_quality_url.startswith('http://') or best_quality_url.startswith('https://'):
                        image_url = best_quality_url
                    else:
                        parsed_url = urlparse(best_quality_url)
                        image_url = 'https://' + parsed_url.netloc + parsed_url.path

                if price_span:
                    price = price_span.find('span').text.strip()
                else:
                    price = None
               
                active_page_element = driver.find_element(By.CSS_SELECTOR, 'div.pagination span.current')
                current_page = int(active_page_element.text)

                product_data = {
                    'product_url': product_url,
                    'image_url': image_url,
                    'product_name': product_name,
                    'product_price': price,
                    'store': store,
                    'current_page': current_page
                }

                save_product(product_data)

        try:
            pager_bottom = driver.find_element(By.CLASS_NAME, 'pagination')
            next_button = pager_bottom.find_element(By.CLASS_NAME, 'next')

            if 'disabled' in next_button.get_attribute('class'):
                break
            
            next_button.click()
            time.sleep(5) 
        except NoSuchElementException:
            print("El botón 'Next' no se encontró en la página actual")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            break

    driver.quit()
    print("******* TIENDA MUNDO VINO FINALIZADA *******")
    return True



