
"""
Publication des donnees agricoles vers Mosquitto.
MQTT v5, QoS 1, Last Will.
"""
import argparse
import json
import os
import sys
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from capteurs import NoeudCapteur, mesure_invalide

load_dotenv()

HOST = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USER = os.getenv("MQTT_USER")
PASSWORD = os.getenv("MQTT_PASSWORD")

DEVICE = os.getenv("DEVICE_ID", "capteur01")
FERME = os.getenv("FERME", "ferme01")
PARCELLE = os.getenv("PARCELLE", "parcelle01")
CA_FILE = os.getenv("MQTT_CA_FILE")

BASE = f"agri/{FERME}/{PARCELLE}/{DEVICE}"
TOPIC_TELEMETRY = f"{BASE}/telemetry"
TOPIC_STATUS = f"{BASE}/status"


def on_connect(client, userdata, flags,
               reason_code, properties):
    if reason_code.is_failure:
        print(f"[ERREUR] Connexion refusee : {reason_code}")
        client.disconnect()
        return

    print(f"[OK] Connecte a {HOST}:{PORT} en tant que "
          f"'{USER or 'anonyme'}'")
    client.publish(
        TOPIC_STATUS, "online", qos=1, retain=True
    )


def on_publish(client, userdata, mid,
               reason_code, properties):
    if reason_code.is_failure:
        print(f"[REFUS] Message {mid} : {reason_code}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--intervalle", type=float, default=5)
    p.add_argument("--nombre", type=int, default=0)
    p.add_argument("--humidite", type=float, default=45)
    p.add_argument("--batterie", type=float, default=100)
    p.add_argument("--invalide", type=int, default=0)
    args = p.parse_args()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=DEVICE,
        protocol=mqtt.MQTTv5
    )

    if USER:
        client.username_pw_set(USER, PASSWORD)

    if CA_FILE:
        client.tls_set(ca_certs=CA_FILE)

    client.will_set(
        TOPIC_STATUS, "offline", qos=1, retain=True
    )
    client.on_connect = on_connect
    client.on_publish = on_publish

    try:
        client.connect(HOST, PORT, keepalive=30)
    except (ConnectionRefusedError, OSError) as e:
        sys.exit(f"[ERREUR] Broker injoignable : {e}")

    client.loop_start()

    for _ in range(50):
        if client.is_connected():
            break
        time.sleep(0.1)

    if not client.is_connected():
        client.loop_stop()
        sys.exit("[ERREUR] Verifier .env et Mosquitto")

    noeud = NoeudCapteur(
        DEVICE,
        humidite_sol=args.humidite,
        batterie=args.batterie
    )

    envoyes = 0

    try:
        while args.nombre == 0 or envoyes < args.nombre:
            mesure = noeud.mesurer()

            if args.invalide and mesure["seq"] % args.invalide == 0:
                mesure = mesure_invalide(mesure)

            info = client.publish(
                TOPIC_TELEMETRY,
                json.dumps(mesure),
                qos=1
            )

            print(
                f"-> {TOPIC_TELEMETRY} (mid={info.mid}) "
                f"{json.dumps(mesure)}"
            )

            envoyes += 1
            time.sleep(args.intervalle)

    except KeyboardInterrupt:
        print("\nArret demande (Ctrl+C)")

    finally:
        client.publish(
            TOPIC_STATUS, "offline",
            qos=1, retain=True
        ).wait_for_publish(2)

        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
