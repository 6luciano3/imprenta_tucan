import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

class DashboardAccessTest(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)

    def test_dashboard_access(self):
        driver = self.driver
        # Cambia estos valores por un usuario válido de tu sistema
        username = "admin"
        password = "admin123"
        
        # Ir a la página de login
        driver.get("http://127.0.0.1:8000/usuarios/login/")
        
        # Completar el formulario de login
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        
        # Esperar a que cargue el dashboard
        time.sleep(2)
        # Guardar captura de pantalla del login exitoso
        driver.save_screenshot("media/selenium_login_ok.png")
        driver.get("http://127.0.0.1:8000/usuarios/dashboard/")
        time.sleep(2)
        # Guardar captura de pantalla del dashboard cargado
        driver.save_screenshot("media/selenium_dashboard_ok.png")
        
        # Verificar que el dashboard se cargó correctamente
        self.assertIn("dashboard", driver.current_url)
        # Puedes agregar más asserts según el contenido esperado

    def tearDown(self):
        self.driver.quit()

if __name__ == "__main__":
    unittest.main()
