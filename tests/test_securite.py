
"""
test_securite.py — Tests d'intrusion LOCAUX sur le Broker Mosquitto sécurisé.
 
À lancer uniquement sur le Broker du TP (127.0.0.1). Chaque test affiche
OK si le comportement observé est celui attendu (refus), ÉCHEC sinon.
  python tests\\test_securite.py
"""
import os
import time
 
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
 
load_dotenv()
HOST = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
CAPTEUR_USER = os.getenv("MQTT_USER", "capteur01")
CAPTEUR_PWD = os.getenv("MQTT_PASSWORD")
SUPERV_PWD = os.getenv("TEST_SUPERVISEUR_PASSWORD")
 
resultats = []
 
 
def connexion(user=None, pwd=None, cid="test"):
    """Tente une connexion MQTT v5 ; renvoie (client, code_retour)."""
    etat = {}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid, protocol=mqtt.MQTTv5)
    if user:
        c.username_pw_set(user, pwd)
    c.on_connect = lambda cl, u, f, rc, p: etat.update(rc=rc)
    c.on_publish = lambda cl, u, mid, rc, p: etat.update(pub=rc)
    c.on_subscribe = lambda cl, u, mid, rcs, p: etat.update(sub=rcs[0])
    c.connect(HOST, PORT, 10)
    c.loop_start()
    for _ in range(30):
        if "rc" in etat:
            break
        time.sleep(0.1)
    c._etat = etat
    return c, etat.get("rc")
 
 
def attendre(etat, cle):
    for _ in range(30):
        if cle in etat:
            return etat[cle]
        time.sleep(0.1)
    return None
 
 
def verifier(nom, refuse, detail):
    resultats.append(refuse)
    print(f"[{'OK' if refuse else 'ÉCHEC'}] {nom} -> {detail}")
 
 
def fermer(c):
    c.loop_stop()
    c.disconnect()
 
 
# T1 — Connexion anonyme
c, rc = connexion(cid="intrus-anonyme")
verifier("T1 connexion anonyme refusée", rc is not None and rc.is_failure, rc)
fermer(c)
 
# T2 — Mauvais mot de passe
c, rc = connexion(CAPTEUR_USER, "mauvais_mot_de_passe", cid="intrus-mdp")
verifier("T2 mauvais mot de passe refusé", rc is not None and rc.is_failure, rc)
fermer(c)
 
# T3 — Le capteur tente d'usurper un autre capteur (publication interdite)
c, rc = connexion(CAPTEUR_USER, CAPTEUR_PWD, cid="capteur01-test")
if rc is not None and not rc.is_failure:
    c.publish("agri/ferme01/parcelle01/capteur02/telemetry", '{"soil_moisture": 1}', qos=1)
    r = attendre(c._etat, "pub")
    verifier("T3 publication sur le topic d'un autre capteur refusée", r is not None and r.is_failure, r)
    # T4 — Le capteur tente d'espionner toutes les données de la ferme.
    # Mosquitto accepte l'abonnement (SUBACK) mais FILTRE chaque message selon l'ACL :
    # on vérifie donc qu'aucun message n'est reçu.
    recus = []
    c.on_message = lambda cl, u, m: recus.append(m.topic)
    c.subscribe("agri/ferme01/#", qos=1)
    attendre(c._etat, "sub")
    c.publish("agri/ferme01/parcelle01/capteur01/telemetry", '{"test": true}', qos=1)
    time.sleep(2)
    verifier("T4 lecture de agri/ferme01/# impossible pour le capteur", len(recus) == 0,
             f"{len(recus)} message(s) reçu(s)")
else:
    verifier("T3/T4 (connexion capteur01 impossible : vérifier .env)", False, rc)
fermer(c)
 
# T5 — Le superviseur (lecture seule) tente d'envoyer une fausse alerte
if SUPERV_PWD:
    c, rc = connexion("superviseur", SUPERV_PWD, cid="superviseur-test")
    c.publish("agri/ferme01/alertes/parcelle01", '{"type": "fausse_alerte"}', qos=1)
    r = attendre(c._etat, "pub")
    verifier("T5 publication d'alerte par le superviseur refusée", r is not None and r.is_failure, r)
    fermer(c)
else:
    print("[--] T5 ignoré : définir TEST_SUPERVISEUR_PASSWORD dans .env")
 
print(f"\nBilan : {sum(resultats)}/{len(resultats)} tests conformes")

