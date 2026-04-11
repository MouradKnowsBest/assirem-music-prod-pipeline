"""
Module _http.py — Utilitaires HTTP partagés

Regroupe les fonctions communes aux modules visual.py, wavespeed.py, youtube.py :
  - Lecture des clés API depuis credentials/
  - Construction des headers HTTP
  - Spinner de progression
  - Polling de statut de génération
  - Téléchargement de fichiers avec retry
"""

import os
import sys
import time
import threading
import requests
from typing import Callable, Optional


def lire_cle_api(base_dir: str, service: str) -> str:
    """
    Lit la clé API depuis credentials/<service>.key
    
    Args:
        base_dir: Répertoire racine du projet
        service: Nom du service (leonardo, wavespeed, etc.)
    
    Returns:
        str: Clé API
    
    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        ValueError: Si le fichier est vide
    """
    path = os.path.join(base_dir, "credentials", f"{service}.key")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Clé API {service} introuvable : {path}\n"
            f"Créez credentials/{service}.key avec votre clé API."
        )
    cle = open(path).read().strip()
    if not cle:
        raise ValueError(f"credentials/{service}.key est vide.")
    return cle


def headers_json(cle: str, auth_prefix: str = "Bearer") -> dict:
    """
    Construit les headers HTTP standard pour une API JSON
    
    Args:
        cle: Clé API
        auth_prefix: Préfixe d'autorisation (Bearer par défaut)
    
    Returns:
        dict: Headers HTTP
    """
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"{auth_prefix} {cle}",
    }


class Spinner:
    """
    Affiche un spinner animé avec temps écoulé
    
    Usage:
        spinner = Spinner("Génération en cours")
        spinner.start()
        # ... opération longue ...
        spinner.stop()
    """
    
    def __init__(self, label: str):
        self.label = label
        self.stop_event = threading.Event()
        self.thread = None
        
    def start(self):
        """Démarre le spinner dans un thread séparé"""
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Arrête le spinner et efface la ligne"""
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=1.0)
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
    
    def _run(self):
        """Thread interne du spinner"""
        syms = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        debut = time.time()
        i = 0
        while not self.stop_event.is_set():
            elapsed = int(time.time() - debut)
            sys.stdout.write(f"\r  {syms[i % len(syms)]} {self.label} ({elapsed}s)")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1


def poll_until_ready(
    check_fn: Callable[[], tuple[bool, Optional[str]]],
    label: str,
    timeout_sec: int = 300,
    interval_sec: int = 5
) -> str:
    """
    Polling jusqu'à ce qu'une condition soit remplie
    
    Args:
        check_fn: Fonction qui retourne (is_ready: bool, result: Optional[str])
        label: Label pour le spinner
        timeout_sec: Timeout en secondes
        interval_sec: Intervalle entre chaque vérification
    
    Returns:
        str: Résultat retourné par check_fn quand ready
    
    Raises:
        TimeoutError: Si le timeout est dépassé
        RuntimeError: Si check_fn retourne une erreur
    """
    spinner = Spinner(label)
    spinner.start()
    
    debut = time.time()
    try:
        while time.time() - debut < timeout_sec:
            ready, result = check_fn()
            if ready:
                spinner.stop()
                return result
            time.sleep(interval_sec)
        
        spinner.stop()
        raise TimeoutError(f"Timeout dépassé ({timeout_sec}s) : {label}")
    except Exception as e:
        spinner.stop()
        raise


def telecharger_fichier(
    url: str,
    dest_path: str,
    max_retries: int = 3,
    timeout: int = 120
) -> None:
    """
    Télécharge un fichier avec retry
    
    Args:
        url: URL du fichier
        dest_path: Chemin de destination
        max_retries: Nombre max de tentatives
        timeout: Timeout en secondes par tentative
    
    Raises:
        RuntimeError: Si toutes les tentatives échouent
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, stream=True)
            resp.raise_for_status()
            
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return  # Succès
            
        except Exception as e:
            if attempt == max_retries:
                raise RuntimeError(
                    f"Échec du téléchargement après {max_retries} tentatives : {url}\n{e}"
                )
            time.sleep(2 ** attempt)  # Backoff exponentiel
