# Workflow n8n — Relances quotidiennes

`relances-quotidiennes.json` orchestre l'envoi des relances de l'etape 6 :

```
Cron 08h00
   → GET https://formations.alex-worksmart.com/api/internal/reminders/due
   → Code "Prepare emails" (formate sujet + HTML selon le type)
   → POST api.resend.com/emails (un par item)
   → Code "Collect reminder_ids"
   → POST .../api/internal/reminders/mark-sent
```

## Import dans n8n

1. n8n → **Workflows** → **Import from File** → choisir `relances-quotidiennes.json`.
2. Le workflow s'ouvre avec 6 nodes connectes. **Ne pas activer encore.**

## Credentials a creer (3 minutes)

n8n → **Credentials** → **+ Add credential** → choisir **HTTP Header Auth** :

### Credential 1 : "Habilitation Internal Secret"

| Champ | Valeur |
|---|---|
| Name | `Habilitation Internal Secret` |
| Header Name | `X-Internal-Secret` |
| Header Value | _ton `REMINDERS_SECRET` du `.env` du backend_ |

### Credential 2 : "Resend API"

| Champ | Valeur |
|---|---|
| Name | `Resend API` |
| Header Name | `Authorization` |
| Header Value | `Bearer re_xxxxxxxx` _(ta cle Resend)_ |

## Brancher les credentials sur le workflow

Apres import, ouvre chaque node HTTP Request et selectionne la bonne credential
(le JSON exporte ne peut pas les referencer directement par ID) :

- **GET reminders/due** → Credential to connect with → `Habilitation Internal Secret`
- **Send via Resend** → Credential to connect with → `Resend API`
- **POST mark-sent** → Credential to connect with → `Habilitation Internal Secret`

## Verification avant activation

1. Clique sur le node **GET reminders/due** → bouton **Execute Node** : tu dois
   recevoir `{items: [...], skipped: [...]}`. Si 401 : credential mal configuree.
2. Si `items` est vide (aucune relance aujourd'hui), tu peux forcer un test en
   creant un dépanneur avec une applicabilite cochée et `required_since` >= 7j
   (ou en supprimant les Reminder du jour pour re-tester).
3. Pour tester l'envoi sans spammer : remplace temporairement le `from`/`to`
   du node "Send via Resend" par ton propre email.

## Activer

Bouton **Active** en haut a droite. Le workflow tournera tous les jours a 08h00
(serveur n8n). Verifie que le fuseau horaire de ton instance n8n est correct.

## Personnalisation

- **Heure d'execution** : modifier l'expression cron du node "Cron 08h00"
  (`0 0 8 * * *` = tous les jours a 8h pile).
- **From email** : actuellement code en dur `habilitations@test.montpellierdepannage.com`
  dans le node "Send via Resend". Si tu changes de domaine, edite le `jsonBody`.
- **Sujets / corps** : modifier le code du node "Prepare emails" (les constantes
  `SUBJECTS` et `INTROS` au debut du script).

## Cas d'echec

- Si Resend retourne une erreur (cle invalide, domaine non verifie, rate limit) :
  le node Send va echouer, l'execution s'arrete, **le mark-sent n'est pas appele**.
  Consequence : le `Reminder` reste avec `sent_at = null` et sera reessaye au
  prochain cron (24h plus tard, avec un nouveau magic_link). C'est OK pour le
  MVP ; pour faire mieux, ajouter un Error Workflow dans n8n.
- Si le backend est down : meme principe, le cron reessayera le lendemain.
