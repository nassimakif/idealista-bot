# 🤖 Idealista Valencia Bot — Setup

## Critères configurés
- 📍 Valencia, tous quartiers
- 💶 Max 1 900€/mois
- 🛏 3 chambres minimum
- 🚿 2 salles de bain minimum
- 🛋 Meublé
- 🌿 Terrasse/jardin
- 📅 Longue durée uniquement

---

## 1. Créer le bot Telegram (1 min)

1. Ouvre Telegram → cherche **@BotFather**
2. Tape `/newbot`, suis les instructions
3. Copie le **token** donné (ex: `123456:ABC-DEF...`)
4. Récupère ton **Chat ID** :
   - Cherche **@userinfobot** sur Telegram
   - Il te donne ton ID (ex: `987654321`)
   - Pour un groupe : ajoute le bot au groupe, envoie un message,
     puis va sur `https://api.telegram.org/botTON_TOKEN/getUpdates`
     et cherche `"chat":{"id":...}`

---

## 2. Installer sur ton VPS

```bash
# Cloner / uploader le dossier
cd ~
mkdir idealista_bot && cd idealista_bot

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
export TELEGRAM_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="987654321"
export CHECK_INTERVAL="3600"   # 1h entre chaque check (en secondes)
```

---

## 3. Lancer le bot

```bash
# Test manuel (une seule vérification)
python bot.py

# En tâche de fond avec tmux (tu connais déjà !)
tmux new-session -d -s idealista 'python bot.py'

# Pour voir les logs
tmux attach -t idealista

# Ou en arrière-plan avec nohup
nohup python bot.py > bot.log 2>&1 &
```

---

## 4. Lancer au démarrage du VPS (optionnel)

Ajoute dans `/etc/crontab` ou avec `crontab -e` :

```
@reboot cd /root/idealista_bot && TELEGRAM_TOKEN="..." TELEGRAM_CHAT_ID="..." python bot.py &
```

---

## 5. Partager avec Marco et Julian

- Crée un **groupe Telegram** avec eux 3
- Ajoute le bot au groupe
- Utilise le **Chat ID du groupe** comme `TELEGRAM_CHAT_ID`
- Tout le monde reçoit les annonces en temps réel

---

## ⚠️ Notes importantes

- **Si le bot se fait bloquer** par Idealista : augmente `CHECK_INTERVAL` à 7200 (2h) ou 10800 (3h).
  Un check toutes les heures reste raisonnable pour un usage perso.
- **Si les annonces ne parsent pas** : Idealista peut changer son HTML.
  Dans ce cas, inspecte la page et ajuste les sélecteurs CSS dans `bot.py`.
- **Base de données** : `annonces.db` stocke toutes les annonces vues.
  Supprime-la pour repartir de zéro.
