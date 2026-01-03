#!/usr/bin/env python3
"""
Script para sincronizar datos de Liga Meiland a Supabase
Alternativa a la Edge Function cuando hay problemas de autorización

Uso:
    python sync_meiland.py

Requisitos:
    pip install requests supabase
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests
from supabase import create_client, Client
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración
MEILAND_BASE = "https://app.meiland.es"
TEAM_ID = "5253"
DIVISION_ID = "699"

# Credenciales desde variables de entorno
MEILAND_EMAIL = os.getenv("MEILAND_EMAIL", "")
MEILAND_PASSWORD = os.getenv("MEILAND_PASSWORD", "")

# Credenciales de Supabase desde variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://teqqqbhgvrcboxzmacaz.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


class MeilandScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.cookies = None
        self.csrf_token = None

    def login(self) -> bool:
        """Login to Meiland and get session cookies"""
        try:
            # Get login page to extract CSRF token
            print("🔐 Obteniendo token CSRF...")
            login_page = self.session.get(f"{MEILAND_BASE}/app/user/login")
            
            # Extract CSRF token
            csrf_match = re.search(r'name="_csrf-backend"\s+value="([^"]+)"', login_page.text)
            if csrf_match:
                self.csrf_token = csrf_match.group(1)
                print(f"✅ CSRF token obtenido")
            else:
                print("⚠️  No se encontró token CSRF")

            # Perform login
            print(f"🔐 Iniciando sesión como {MEILAND_EMAIL}...")
            login_data = {
                "LoginForm[email]": MEILAND_EMAIL,
                "LoginForm[password]": MEILAND_PASSWORD,
                "LoginForm[rememberMe]": "1",
            }
            if self.csrf_token:
                login_data["_csrf-backend"] = self.csrf_token

            login_response = self.session.post(
                f"{MEILAND_BASE}/app/user/login",
                data=login_data,
                allow_redirects=False
            )

            # Check if login was successful
            if login_response.status_code in [302, 200]:
                print("✅ Login exitoso")
                return True
            else:
                print(f"❌ Login fallido con código {login_response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error durante login: {e}")
            return False

    def fetch_team_data(self) -> Tuple[List[Dict], Optional[Dict], webdriver.Chrome]:
        """Fetch team page and extract players and next match using Selenium"""
        print(f"\n📊 Obteniendo datos del equipo con Selenium (ID: {TEAM_ID})...")
        
        # Configurar Selenium
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Ejecutar sin ventana
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Primero ir a la página base para establecer cookies
        driver.get(MEILAND_BASE)
        
        # Agregar cookies de sesión desde requests.session
        for cookie in self.session.cookies:
            driver.add_cookie({
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain if cookie.domain else '.meiland.es',
                'path': cookie.path if cookie.path else '/'
            })
        
        # Ir a la página del equipo
        driver.get(f"{MEILAND_BASE}/app/team/view?id={TEAM_ID}")
        
        # Esperar a que AngularJS cargue los datos (esperar por ng-repeat)
        print("  ⏳ Esperando que AngularJS cargue los datos...")
        time.sleep(3)  # Dar tiempo a AngularJS para renderizar
        
        players = []
        
        # Extraer jugadores con Selenium
        player_rows = driver.find_elements(By.CSS_SELECTOR, 'div[ng-repeat*="player in players"]')
        
        for row in player_rows:
            try:
                # Extraer nombre del jugador
                text = row.text.split('\n')[0]  # Primera línea tiene el nombre
                name_match = re.match(r'([^-]+?)\s*-\s*(?:player|keeper)', text)
                
                if name_match:
                    name = name_match.group(1).strip()
                    
                    # Extraer stats de los divs center_all
                    stat_divs = row.find_elements(By.CSS_SELECTOR, 'div.center_all')
                    
                    if len(stat_divs) >= 2:
                        # Los primeros 3 son: partidos, goles, faltas
                        games = stat_divs[0].text.split('\n')[0].strip()
                        goals = stat_divs[1].text.split('\n')[0].strip()
                        
                        players.append({
                            "name": name,
                            "games_played": int(games) if games.isdigit() else 0,
                            "goals": int(goals) if goals.isdigit() else 0,
                        })
            except Exception as e:
                print(f"  ⚠️  Error procesando jugador: {e}")
                continue
        
        print(f"✅ {len(players)} jugadores encontrados")
        
        # Extraer próximo partido
        next_match = None
        try:
            next_match_date = driver.find_element(By.XPATH, '//div[@class="meilandBox"]//a[contains(@href, "/app/match/view")]').text
            teams = driver.find_elements(By.XPATH, '//div[@class="meilandBox"]//a[contains(@href, "/app/team/view")]')
            
            if len(teams) >= 2:
                team1 = teams[0].text.split('\n')[-1]  # Última línea tiene el nombre
                team2 = teams[1].text.split('\n')[-1]
                
                next_match = {
                    "date_time": next_match_date,
                    "home_team": team1,
                    "away_team": team2,
                }
                print(f"✅ Próximo partido: {team1} vs {team2} - {next_match_date}")
        except Exception as e:
            print(f"  ℹ️  No se pudo extraer próximo partido: {e}")
        
        # Devolvemos el driver para reutilizarlo
        return players, next_match, driver

    def fetch_division_data(self, driver) -> Tuple[List[Dict], List[Dict]]:
        """Fetch division page and extract matches using Selenium"""
        print(f"\n⚽ Obteniendo calendario de partidos con Selenium...")
        
        try:
            # Ya estamos en la página del equipo, hacer clic en "Ver calendario"
            print("  ⏳ Esperando modal de calendario...")
            time.sleep(1)
            
            # Hacer clic en el botón de calendario
            try:
                calendar_button = driver.find_element(By.ID, 'matchButton')
                calendar_button.click()
                time.sleep(1)  # Esperar a que el modal aparezca
            except Exception as e:
                print(f"  ℹ️  No se pudo abrir modal: {e}")
            
            matches = []
            standings = []
            
            # Extraer partidos de la tabla
            match_rows = driver.find_elements(By.CSS_SELECTOR, 'tr[data-key]')
            
            for row in match_rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, 'td')
                    match_id = row.get_attribute('data-key')
                    
                    if len(cells) >= 5:
                        # Células: [jornada, fecha, local, visitante, resultado]
                        date_text = cells[1].text
                        home_team = cells[2].text.split('\n')[-1].strip()
                        away_team = cells[3].text.split('\n')[-1].strip()
                        result = cells[4].text.strip()
                        
                        # Extraer fecha
                        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_text)
                        date_str = date_match.group(1) if date_match else None
                        
                        # Parsear resultado
                        home_score = None
                        away_score = None
                        if result and result != "-":
                            score_parts = result.split("-")
                            if len(score_parts) == 2:
                                try:
                                    home_score = int(score_parts[0].strip())
                                    away_score = int(score_parts[1].strip())
                                except ValueError:
                                    pass
                        
                        match_data = {
                            "date": date_str,
                            "home_team": home_team,
                            "away_team": away_team,
                            "home_score": home_score,
                            "away_score": away_score,
                            "match_id": match_id,
                            "scorers": []  # Lo llenaremos después
                        }
                        matches.append(match_data)
                except Exception as e:
                    print(f"  ⚠️  Error procesando partido: {e}")
                    continue
            
            print(f"✅ {len(matches)} partidos encontrados")
            
            # Ahora extraer goleadores de cada partido JUGADO
            played_matches = [m for m in matches if m["home_score"] is not None and m["match_id"]]
            print(f"\n⚽ Extrayendo goleadores de {len(played_matches)} partidos jugados...")
            
            for match in played_matches:
                try:
                    print(f"  📄 Visitando partido {match['match_id']}: {match['home_team']} vs {match['away_team']}...")
                    scorers_data = self.fetch_match_scorers(driver, match["match_id"], match["home_team"], match["away_team"])
                    match["madagascar_scorers"] = scorers_data["madagascar_scorers"]
                    match["rival_scorers"] = scorers_data["rival_scorers"]
                    
                    if scorers_data["madagascar_scorers"] or scorers_data["rival_scorers"]:
                        mg_names = ", ".join([f"{s['name']} ({s['goals']})" for s in scorers_data["madagascar_scorers"]])
                        rv_names = ", ".join([f"{s['name']} ({s['goals']})" for s in scorers_data["rival_scorers"]])
                        print(f"    ⚽ Madagascar: {mg_names or 'Sin goles'}")
                        print(f"    ⚽ Rival: {rv_names or 'Sin goles'}")
                    else:
                        print(f"    ℹ️  No se encontraron goleadores")
                except Exception as e:
                    print(f"  ⚠️  Error: {e}")
            
            print("ℹ️  Clasificación no disponible desde esta página")
            
            return standings, matches
            
        except Exception as e:
            driver.quit()
            raise e
        finally:
            # Solo cerrar si no hay excepción
            pass
    
    def fetch_match_scorers(self, driver, match_id: str, home_team: str, away_team: str) -> Dict:
        """Fetch scorers from a specific match, separated by team"""
        try:
            # Ir a la página del partido
            driver.get(f"{MEILAND_BASE}/app/match/view?id={match_id}")
            time.sleep(4)  # Esperar más tiempo para AngularJS
            
            madagascar_scorers = []
            rival_scorers = []
            
            # Buscar las tablas de goles (Goles Equipo 1 y Goles Equipo 2)
            try:
                # Encontrar todas las tablas precedidas por "Goles Equipo"
                goals_sections = driver.find_elements(By.XPATH, "//h4[contains(text(), 'Goles Equipo')]")
                
                if not goals_sections:
                    goals_sections = driver.find_elements(By.XPATH, "//h4[@class='box-title' and contains(text(), 'Goles')]")
                
                is_madagascar_home = "Madagascar" in home_team
                
                for idx, section in enumerate(goals_sections):
                    # idx 0 = Equipo 1 (local), idx 1 = Equipo 2 (visitante)
                    is_madagascar_section = (idx == 0 and is_madagascar_home) or (idx == 1 and not is_madagascar_home)
                    
                    try:
                        parent = section.find_element(By.XPATH, "./parent::*/parent::*")
                        table = parent.find_element(By.TAG_NAME, 'table')
                        rows = table.find_elements(By.CSS_SELECTOR, 'tr[data-key]')
                        
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) >= 1:
                                try:
                                    name_element = cells[0].find_element(By.TAG_NAME, 'a')
                                    scorer_name = name_element.text.strip()
                                    
                                    if scorer_name:
                                        target_list = madagascar_scorers if is_madagascar_section else rival_scorers
                                        existing = next((s for s in target_list if s["name"] == scorer_name), None)
                                        if existing:
                                            existing["goals"] += 1
                                        else:
                                            target_list.append({"name": scorer_name, "goals": 1})
                                except:
                                    continue
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"    ⚠️  Error buscando goles: {e}")
            
            return {
                "madagascar_scorers": madagascar_scorers,
                "rival_scorers": rival_scorers
            }
            
        except Exception as e:
            print(f"    ⚠️  Error en fetch_match_scorers: {e}")
            return {"madagascar_scorers": [], "rival_scorers": []}


def sync_to_supabase(players: List[Dict], standings: List[Dict], matches: List[Dict]):
    """Sync data to Supabase"""
    print("\n🔄 Sincronizando con Supabase...")
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    
    results = {
        "players": {"updated": 0, "errors": 0},
        "standings": {"updated": 0, "errors": 0},
        "matches": {"updated": 0, "errors": 0},
    }

    # Sync players
    print("\n👥 Sincronizando jugadores...")
    for player in players:
        try:
            # Intentar con todos los campos
            player_data = {
                "name": player["name"],
                "goals": player["goals"],
                "games_played": player["games_played"],
                "updated_at": datetime.now().isoformat(),
            }
            supabase.table("players").upsert(player_data, on_conflict="name").execute()
            results["players"]["updated"] += 1
        except Exception as e:
            print(f"  ❌ Error con {player['name']}: {e}")
            results["players"]["errors"] += 1

    print(f"  ✅ {results['players']['updated']} jugadores actualizados")

    # Sync standings
    print("\n📊 Sincronizando clasificación...")
    for standing in standings:
        try:
            supabase.table("standings").upsert({
                **standing,
                "updated_at": datetime.now().isoformat(),
            }).execute()
            results["standings"]["updated"] += 1
        except Exception as e:
            print(f"  ❌ Error con {standing['team_name']}: {e}")
            results["standings"]["errors"] += 1

    print(f"  ✅ {results['standings']['updated']} equipos actualizados")

    # Sync matches
    print("\n⚽ Sincronizando partidos...")
    for match in matches:
        try:
            # Convert date format
            match_date = match["date"]
            if match_date and "/" in match_date:
                parts = match_date.split("/")
                if len(parts) == 3:
                    match_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

            is_madagascar_home = "Madagascar" in match["home_team"]
            
            # Preparar datos del partido
            match_data = {
                "match_date": match_date,
                "opponent": match["away_team"] if is_madagascar_home else match["home_team"],
                "goals_for": match["home_score"] if is_madagascar_home else match["away_score"],
                "goals_against": match["away_score"] if is_madagascar_home else match["home_score"],
                "is_home": is_madagascar_home,
                "competition": "Liga Meiland",
                "updated_at": datetime.now().isoformat(),
            }
            
            # Agregar goleadores separados por equipo
            if match.get("madagascar_scorers") or match.get("rival_scorers"):
                import json
                notes_data = {
                    "madagascar_scorers": match.get("madagascar_scorers", []),
                    "rival_scorers": match.get("rival_scorers", [])
                }
                match_data["notes"] = json.dumps(notes_data, ensure_ascii=False)
            
            supabase.table("matches").upsert(match_data, on_conflict="match_date,opponent").execute()
            results["matches"]["updated"] += 1
        except Exception as e:
            print(f"  ❌ Error con partido: {e}")
            results["matches"]["errors"] += 1

    print(f"  ✅ {results['matches']['updated']} partidos actualizados")

    return results


def main():
    print("=" * 60)
    print("🏆 MADAGASCAR FC - SYNC MEILAND → SUPABASE")
    print("=" * 60)

    # Validate credentials
    if not MEILAND_EMAIL or not MEILAND_PASSWORD:
        print("\n❌ ERROR: Crea un archivo .env con tus credenciales")
        print("   Copia .env.example como .env y completa los datos")
        print("\n   Ver SYNC_README.md para instrucciones")
        return
    
    if not SUPABASE_SERVICE_ROLE_KEY:
        print("\n❌ ERROR: Falta SUPABASE_SERVICE_ROLE_KEY en el archivo .env")
        return

    scraper = MeilandScraper()

    # Step 1: Login
    if not scraper.login():
        print("\n❌ No se pudo iniciar sesión en Meiland")
        return

    # Step 2: Fetch data
    players, next_match, driver = scraper.fetch_team_data()
    standings, matches = scraper.fetch_division_data(driver)
    
    # Cerrar driver después de todo
    if driver:
        driver.quit()

    # Step 3: Sync to Supabase
    results = sync_to_supabase(players, standings, matches)

    # Summary
    print("\n" + "=" * 60)
    print("✅ SINCRONIZACIÓN COMPLETADA")
    print("=" * 60)
    print(f"👥 Jugadores: {results['players']['updated']} actualizados, {results['players']['errors']} errores")
    print(f"📊 Clasificación: {results['standings']['updated']} actualizados, {results['standings']['errors']} errores")
    print(f"⚽ Partidos: {results['matches']['updated']} actualizados, {results['matches']['errors']} errores")
    print(f"🕐 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
