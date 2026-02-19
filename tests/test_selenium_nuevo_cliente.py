import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

class NuevoClienteTest(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)

    def test_alta_nuevo_cliente(self):
        driver = self.driver
        username = "admin"
        password = "admin123"

        # Login
        driver.get("http://127.0.0.1:8000/usuarios/login/")
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(2)

        # Ir a la página de alta de cliente (URL corregida)
        driver.get("http://127.0.0.1:8000/clientes/crear/")
        time.sleep(2)
        driver.save_screenshot("media/cliente_formulario_vacio.png")

        # Completar formulario con los names correctos
        driver.find_element(By.NAME, "nombre").send_keys("Cliente Selenium")
        driver.find_element(By.NAME, "apellido").send_keys("Test")
        driver.find_element(By.NAME, "email").send_keys("selenium_cliente@ejemplo.com")
        driver.find_element(By.NAME, "razon_social").send_keys("Selenium S.A.")
        driver.find_element(By.NAME, "telefono").send_keys("3811234567")
        driver.find_element(By.NAME, "celular").send_keys("3817654321")
        driver.find_element(By.NAME, "direccion").send_keys("Calle Falsa 123")
        driver.find_element(By.NAME, "provincia").send_keys("Tucumán")
        driver.find_element(By.NAME, "pais").send_keys("Argentina")
        # Selects (si existen opciones por defecto, Selenium puede seleccionar la primera)
        try:
            driver.find_element(By.NAME, "ciudad").send_keys("San Miguel de Tucumán")
        except Exception:
            pass
        try:
            driver.find_element(By.NAME, "estado").send_keys("Activo")
        except Exception:
            pass
        driver.save_screenshot("media/cliente_formulario_completado.png")

        # Enviar formulario
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(2)
        driver.save_screenshot("media/cliente_alta_exito.png")

        # Verificar que el cliente aparece en la lista
        driver.get("http://127.0.0.1:8000/clientes/lista/")
        time.sleep(2)
        driver.save_screenshot("media/cliente_lista.png")
        self.assertIn("Cliente Selenium", driver.page_source)

    def tearDown(self):
        self.driver.quit()

if __name__ == "__main__":
    unittest.main()