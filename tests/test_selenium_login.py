from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

# Ejemplo: Prueba funcional Selenium para login en Django

def test_login():
    driver = webdriver.Chrome()  # Asegúrate de tener chromedriver en PATH
    driver.get('http://127.0.0.1:8000/login/')

    # Espera a que cargue la página
    time.sleep(2)

    # Completa el formulario de login
    username_input = driver.find_element(By.NAME, 'username')
    password_input = driver.find_element(By.NAME, 'password')
    username_input.send_keys('admin')
    password_input.send_keys('adminpassword')
    password_input.send_keys(Keys.RETURN)

    # Espera a que cargue la siguiente página
    time.sleep(2)

    # Verifica que el login fue exitoso (por ejemplo, buscando el dashboard)
    assert 'Dashboard' in driver.page_source

    driver.quit()

if __name__ == '__main__':
    test_login()
