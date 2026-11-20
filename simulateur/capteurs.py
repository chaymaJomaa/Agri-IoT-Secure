
"""
capteurs.py — Couche PERCEPTION simulée.

Modélise un nœud de capteurs placé dans une parcelle :
  - humidité du sol (%)      : diminue avec l'évaporation, remonte après pluie/irrigation
  - température de l'air (°C): cycle jour/nuit + bruit
  - humidité de l'air (%)    : évolue à l'inverse de la température
  - batterie (%)             : se décharge un peu à chaque émission
Aucun matériel n'est nécessaire : les valeurs sont générées par un modèle simple.
"""
import json
import math
import random
import sys
import time

class NoeudCapteur:
    """Nœud de capteurs simulé d'une parcelle agricole."""

    def __init__(self, device_id, humidite_sol=45.0, batterie=100.0, graine=None):
        self.device_id = device_id
        self.humidite_sol = humidite_sol      # % volumique
        self.batterie = batterie              # %
        self.seq = 0                          # numéro de séquence (détection des pertes)
        self.rng = random.Random(graine)      # graine fixe => simulation reproductible

    def _temperature(self, t):
        """Cycle journalier accéléré : 1 jour simulé = 240 s réelles."""
        phase = 2 * math.pi * (t % 240) / 240
        return 24 + 8 * math.sin(phase) + self.rng.gauss(0, 0.4)

    def mesurer(self):
        """Produit une mesure complète sous forme de dictionnaire."""
        t = time.time()
        temperature = self._temperature(t)
        # Évaporation : plus il fait chaud, plus le sol s'assèche
        self.humidite_sol -= max(0.0, 0.15 + 0.04 * (temperature - 20))
        # Petite probabilité de pluie
        if self.rng.random() < 0.02:
            self.humidite_sol += self.rng.uniform(8, 15)
        self.humidite_sol = min(max(self.humidite_sol + self.rng.gauss(0, 0.3), 5.0), 95.0)
        humidite_air = min(max(85 - 1.5 * (temperature - 15) + self.rng.gauss(0, 2), 20.0), 100.0)
        self.batterie = max(0.0, self.batterie - 0.05)
        self.seq += 1
        return {
            "device_id": self.device_id,
            "seq": self.seq,
            "ts": int(t * 1000),                       # horodatage en millisecondes (UTC)
            "soil_moisture": round(self.humidite_sol, 1),
            "temperature": round(temperature, 1),
            "air_humidity": round(humidite_air, 1),
            "battery": round(self.batterie, 1),
        }

    def irriguer(self, apport=20.0):
        """Simule un arrosage (utile pour tester le retour à la normale)."""
        self.humidite_sol = min(self.humidite_sol + apport, 95.0)

DEFAUTS = ("hors_plage", "champ_manquant", "type_errone")

def mesure_invalide(mesure, defaut=None, rng=random):
    """Corrompt volontairement une mesure (tests de qualité des données).

    defaut : "hors_plage", "champ_manquant" ou "type_errone" ;
             None => un des trois défauts est tiré au hasard.
    """
    m = dict(mesure)                           # copie : la mesure d'origine reste intacte
    if defaut is None:
        defaut = rng.choice(DEFAUTS)
    if defaut == "hors_plage":
        m["soil_moisture"] = 180.0             # impossible : > 100 %
    elif defaut == "champ_manquant":
        m.pop("temperature")                   # champ obligatoire absent
    elif defaut == "type_errone":
        m["air_humidity"] = "N/A"              # chaîne au lieu d'un nombre
    else:
        raise ValueError(f"défaut inconnu : {defaut} (attendu : {', '.join(DEFAUTS)})")
    return m

if __name__ == "__main__":
    noeud = NoeudCapteur("capteur01", graine=42)
    if "--invalides" in sys.argv:
        # Test de corruption : une mesure pour chacun des trois défauts, au format JSON
        for defaut in DEFAUTS:
            print(f"{defaut:15s}", json.dumps(mesure_invalide(noeud.mesurer(), defaut), ensure_ascii=False))
        sys.exit(0)
    # Test autonome : 5 mesures affichées dans le terminal, sans réseau
    for _ in range(5):
        print(json.dumps(noeud.mesurer(), ensure_ascii=False))
        time.sleep(1)

