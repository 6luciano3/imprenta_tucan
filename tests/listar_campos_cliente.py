from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# Configuración
url = "http://127.0.0.1:8000/clientes/crear/"
driver = webdriver.Chrome()
driver.implicitly_wait(10)

try:
    driver.get(url)
    time.sleep(2)
    print("Campos <input> con atributo name:")
    for input_elem in driver.find_elements(By.TAG_NAME, "input"):
        name = input_elem.get_attribute("name")
        if name:
            print(f"input: name='{name}'")
    print("\nCampos <select> con atributo name:")
    for select_elem in driver.find_elements(By.TAG_NAME, "select"):
        name = select_elem.get_attribute("name")
        if name:
            print(f"select: name='{name}'")
    print("\nCampos <textarea> con atributo name:")
    for textarea_elem in driver.find_elements(By.TAG_NAME, "textarea"):
        name = textarea_elem.get_attribute("name")
        if name:
            print(f"textarea: name='{name}'")
finally:
    driver.quit()
