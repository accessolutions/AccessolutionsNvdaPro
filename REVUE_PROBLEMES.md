# Revue des problèmes — Accessolutions NVDA Pro

Date de la revue : 25 août 2026

## Verdict

La syntaxe et les diagnostics statiques sont propres. Les problèmes techniques
traités à partir du point 10 sont corrigés ou explicitement bornés. L’extension
nécessite encore une validation sur NVDA réel avant publication.

Cette revue porte sur l’état du dépôt après les dernières modifications. Les
correctifs appliqués au flux d’assistance, au dialogue d’installation et au
geste de débogage sont décrits aux points 1 à 3 ; les autres problèmes restent
à traiter.

## Contrôles effectués

- AST Python valide pour les 11 fichiers Python du dépôt.
- Aucun diagnostic signalé par VS Code.
- Aucune erreur de formatage signalée par `git diff --check`.
- Tests unitaires présents pour les contrôles principaux de l’updater dans [tests/test_updater.py](tests/test_updater.py).
- Aucun test d’exécution effectué avec NVDA réel, NVDA Remote ou wxPython.
- La compatibilité déclarée avec NVDA 2026.1 reste donc à confirmer en situation réelle.

## Problèmes bloquants

### 1. Assistance à distance : saisie de la clé du support (traité)

Le point 1 a été traité dans [remoteRequests.py](globalPlugins/AccessolutionsNvdaPro/remoteRequests.py#L1-L82).

Le fonctionnement est maintenant le suivant :

- l’utilisateur saisit la clé fournie par le support dans une zone d’édition lisible par le lecteur d’écran ;
- les boutons `OK` et `Annuler` sont proposés ;
- une clé vide est refusée ;
- la clé n’est pas enregistrée par l’extension ;
- la clé est encodée correctement dans l’URL `nvdaremote://` ;
- l’URL est ouverte uniquement après validation par l’utilisateur ;
- l’ancienne page HTML contenant la clé fixe a été supprimée ;
- les documentations française et anglaise ont été réalignées.

La connexion reste dépendante du gestionnaire du protocole `nvdaremote://` fourni
par NVDA Remote. L’extension ne contacte pas directement un service HTTP et ne
gère pas elle-même la déconnexion ; celle-ci doit être effectuée depuis NVDA
Remote.

Le point doit encore être validé avec une installation réelle de NVDA Remote,
notamment avec une clé contenant des espaces ou des caractères spéciaux, ainsi
qu’avec une clé vide et l’annulation de la boîte de dialogue.

### 2. Appel incorrect de l’API d’installation NVDA (traité)

Le plugin n’implémente plus une copie locale du dialogue d’installation. Il
ouvre maintenant le dialogue officiel « Installer NVDA » de NVDA depuis
[instAccesso.py](globalPlugins/instAccesso.py#L13-L33).

Cette solution laisse NVDA gérer lui-même :

- la détection d’une nouvelle installation ou d’une mise à jour ;
- l’avertissement en cas de rétrogradation ;
- la conservation ou la création du raccourci du bureau ;
- l’appel à `doInstall()` avec des arguments nommés dans NVDA ;
- la copie de la configuration portable vers le compte utilisateur courant.

Avant l’ouverture du dialogue, les options de démarrage à l’ouverture de
Windows et de copie de la configuration sont temporairement activées afin que
la personne puisse valider directement avec Entrée. Les valeurs originales
des arguments de NVDA sont restaurées immédiatement après la création du
dialogue. Le dialogue officiel reste responsable de désactiver la copie si
NVDA détermine qu’elle n’est pas applicable.

La validation doit encore être effectuée avec une installation réelle de NVDA,
notamment pour confirmer le comportement du raccourci, de l’élévation UAC et
de la copie de configuration depuis une version portable personnalisée.

### 3. Geste du mode debug modernisé (traité)

Le geste de [debugMode.py](globalPlugins/debugMode.py) n’utilise plus
`versionInfo.isTestVersion`, qui n’est plus disponible dans NVDA moderne et ne
contrôlait de toute façon pas la journalisation.

`Win+Ctrl+Shift+D` utilise maintenant la déclaration moderne `@script` et
agit directement sur le niveau de journalisation de NVDA :

- le premier appui mémorise le niveau effectif et active temporairement
  `DEBUG` ;
- le second appui restaure le niveau précédemment actif ;
- la restauration est également effectuée lors de la désactivation de
  l’extension ;
- aucune sauvegarde automatique de la configuration n’est effectuée ;
- les niveaux imposés par la ligne de commande ou le mode sécurisé ne sont pas
  contournés et sont signalés à l’utilisateur.

Le niveau `DEBUG` peut enregistrer des informations sensibles. Le geste doit
être utilisé uniquement pendant un diagnostic et désactivé dès que possible.
Une validation avec NVDA réel reste nécessaire.

## Problèmes majeurs

### 4. Recherche incrémentale (corrigée et améliorée)

La recherche incrémentale est une fonction entièrement virtuelle : elle n’ouvre
aucune fenêtre et n’envoie aucune touche à la page web. Depuis
[rechercheIncrementale.py](globalPlugins/rechercheIncrementale.py), l’utilisateur
appuie sur `Ctrl+I`, puis saisit directement le texte recherché.

Le comportement est maintenant le suivant :

- chaque caractère saisi, ainsi que `Retour arrière`, déclenche rapidement une
  nouvelle recherche ;
- la recherche commence au début du document et sélectionne la première
  occurrence trouvée ;
- le curseur virtuel de NVDA est déplacé sur cette occurrence et sa ligne est
  annoncée ;
- l’annonce précédente est annulée avant la nouvelle afin d’éviter les
  empilements de parole pendant une saisie rapide ;
- `Échap` annule la recherche, `Entrée` la termine et `Tab` ou `Maj+Tab` la
  termine avant de transmettre la touche à NVDA ;
- la capture clavier est libérée après quatre secondes d’inactivité, à l’arrêt
  du module ou si l’utilisateur change de document ;
- une autre capture clavier active n’est jamais remplacée.

La double séquence de parole a été supprimée et le module ne modifie plus
`_lastFindText`, attribut privé du gestionnaire de recherche de NVDA. La seule
limite technique restante est l’utilisation isolée de `_captureFunc`, car NVDA
n’expose pas d’API publique pour intercepter temporairement les gestes. Cette
dépendance est vérifiée avant chaque installation ou libération de la capture.

La fonction doit encore être validée avec NVDA réel dans Firefox et Chromium,
notamment avec une saisie rapide, `Échap`, `Entrée`, `Tab`, `Retour arrière`,
les caractères accentués et un changement de page pendant la recherche.

### 5. Restauration dans le Bloc-notes (corrigée)

Dans [notepad.py](appModules/notepad.py), `focus.appModule` est temporairement
remplacé par `None` pour éviter l’appel récursif lors du routage braille.

La restauration est maintenant placée dans un bloc `try/finally`. Ainsi, une
exception dans `findScript()`, `executeGesture()` ou `gesture.send()` ne laisse
pas l’objet dans un état corrompu.

L’exception nue du traitement de [notepad.py](appModules/notepad.py) a
également été remplacée par les exceptions ciblées `AttributeError`,
`IndexError` et `TypeError`. Les exceptions système telles que
`KeyboardInterrupt` et `SystemExit` ne sont donc plus interceptées.

Le comportement doit encore être vérifié avec NVDA réel et un clavier braille,
notamment en cas d’erreur pendant l’exécution d’un geste.

### 6. Monkey patch global de Firefox (supprimé)

Le fichier `patch_webaccess_firefox.py` a été supprimé. Il remplaçait
directement `Gecko_ia2.Gecko_ia2.__contains__`, une méthode interne de NVDA,
sans restauration et sans contrôle fiable de la version de NVDA.

Ce code ne corrigeait pas la reconnaissance du raccourci `NVDA+F7` : il
modifiait uniquement un test interne d’appartenance d’objet. Les versions
modernes de NVDA gèrent elles-mêmes la liste des éléments et son fonctionnement
en mode formulaire. Le correctif global pouvait donc créer davantage de
régressions que de fiabilité.

La compatibilité avec les anciennes versions est maintenant isolée dans
[manageNVDAF7.py](globalPlugins/manageNVDAF7.py), qui ne redéfinit `NVDA+F7`
que lorsque l’attribut natif `ignoreTreeInterceptorPassThrough` n’est pas
disponible. Le script est exécuté via `scriptHandler.executeScript()` afin de
conserver la gestion normale des erreurs et des appuis répétés.

### 7. Texte braille (corrigé)

Le caractère de remplacement Unicode a été supprimé dans
[accesso_brl.py](globalPlugins/accesso_brl.py#L24-L27). L’annonce utilise
maintenant le texte correctement encodé « Braille intégral ».

Une vérification avec NVDA réel reste recommandée pour confirmer l’annonce
vocale après le changement de table braille.

## Problèmes importants

### 8. Chargement répété des gestes (corrigé)

`loadNavGestures()` dans
[__init__.py](globalPlugins/AccessolutionsNvdaPro/__init__.py#L27-L91) retire
maintenant, avant chaque chargement, les associations connues de
`gestures.ini` dans la carte globale de NVDA.

La suppression est ciblée sur le module, la classe, le script et le geste de
l’extension. Elle est répétée jusqu’à ce qu’il n’existe plus de doublon, puis
le fichier est chargé une seule fois. Les sauvegardes successives des
paramètres ne peuvent donc plus empiler les mêmes associations.

### 9. Mode de parole d’OpenBook (corrigé)

[obu.py](appModules/obu.py) mémorise maintenant le mode de parole actif avant
de désactiver la parole à l’entrée dans OpenBook. Le mode mémorisé est restauré
à la perte du focus, au lieu d’imposer systématiquement le mode `talk`.

Une entrée répétée dans l’application ne remplace pas la valeur mémorisée par
le mode `off`. Le mode est également restauré lors de l’arrêt du module pour
éviter de laisser NVDA silencieux si OpenBook est fermé ou si l’extension est
rechargée depuis son état actif.

Le code utilise l’API moderne de NVDA lorsqu’elle est disponible et conserve
un chemin de compatibilité pour les versions plus anciennes déclarées dans le
manifeste. Les événements `event_appModule_gainFocus()` et
`event_appModule_loseFocus()` sont des événements spéciaux d’app module ;
l’absence de `nextHandler()` n’est donc pas le problème ici.

### 10. Updater sécurisé (corrigé, signature externe restante)

Les contrôles de [updater.py](globalPlugins/AccessolutionsNvdaPro/updater.py) ont été renforcés :

- le gestionnaire de redirection compte réellement les redirections et refuse toute cible qui n’est pas HTTPS ou qui ne figure pas dans l’allowlist GitHub ;
- `_parse_sha256()` n’accepte que des lignes de somme conventionnelles et refuse les contenus ambigus ; il associe également l’empreinte au nom du paquet attendu ;
- le manifeste `manifest.ini` du paquet est inspecté avant l’écriture du fichier temporaire et sa version doit correspondre à `UpdateInfo.version` ;
- `UpdateManager.terminate()` signale l’annulation aux workers et ferme la réponse réseau active lorsque cela est possible, sans bloquer le thread principal de NVDA ;
- les écritures restent interdites en mode sécurisé et la comparaison SHA-256 utilise `hmac.compare_digest()`.

Le SHA-256 ne prouve pas l’authenticité de l’éditeur. Une signature de release
vérifiable par l’extension nécessiterait une clé publique distribuée avec
NVDA et une clé privée conservée par le projet ; ce mécanisme ne peut pas être
inventé sans cette infrastructure.

### 11. Gestion de `NVDA+F7` (corrigée)

[manageNVDAF7.py](globalPlugins/manageNVDAF7.py) ne redéfinit plus le geste
standard sur les versions modernes de NVDA. Sur les versions anciennes, le
relais n’est activé que si NVDA ne marque pas la commande native comme
compatible avec le mode formulaire.

Les appels à `getScript()` sont protégés, le script retourné passe par
`scriptHandler.executeScript()`, et la commande possède une description pour
l’aide à la saisie. Cela évite le conflit permanent avec la liste standard des
éléments et supprime le message trompeur « pas de lien ».

### 12. Chaînes et interface partiellement non traduisibles (corrigé)

Les chaînes visibles des menus, de l’updater, du Bloc-notes, du braille et de
l’installateur sont maintenant enveloppées dans `_()`. Les modules autonomes
initialisent chacun `addonHandler.initTranslation()`, et le geste d’assistance
utilise la déclaration moderne avec une description localisable.

## Autres observations

### 13. Gestion du cycle de vie du plugin principal (corrigée)

Le plugin principal possède maintenant une méthode `terminate()` dans [__init__.py](globalPlugins/AccessolutionsNvdaPro/__init__.py#L144-L147), ce qui est positif.

Les handlers du menu sont maintenant mémorisés puis déconnectés avant la
destruction du menu. Les deux `wx.CallLater()` de démarrage sont conservés et
annulés à l’arrêt. Le panneau de paramètres utilise un marqueur de sauvegarde
explicite afin que `postSave()` ne réutilise pas un état incomplet. L’arrêt
annule aussi les requêtes updater et décharge les gestes de navigation.

### 14. Conflits de raccourcis (réduits et documentés)

Le fichier [gestures.ini](globalPlugins/AccessolutionsNvdaPro/gestures.ini) remplace
certains raccourcis standards du mode navigation uniquement lorsque l’utilisateur
active l’option correspondante. Les entrées qui désactivaient `M`, `Maj+M`, `,`
et `Maj+,` sans commande de remplacement ont été supprimées.

Risques :

- conflits avec NVDA ou d’autres extensions ;
- perte de raccourcis connus des utilisateurs NVDA ;
- comportement variable selon l’ordre de chargement des cartes de gestes ;
- associations globales difficiles à isoler d’une autre extension utilisant les
  mêmes gestes.

Les gestes restants sont documentés dans les deux notices et l’option est
activée par défaut pour conserver le comportement JAWS attendu. L’utilisateur
peut la désactiver pour retrouver les gestes standards de NVDA. Un test avec
les autres extensions et une carte de gestes utilisateur reste nécessaire avant
un déploiement large.

### 15. Manifeste et compatibilité déclarée

Le manifeste est syntaxiquement acceptable dans [manifest.ini](manifest.ini#L6-L10), avec :

- version `2026.08.26.0001` ;
- `minimumNVDAVersion = 2026.1.0` ;
- `lastTestedNVDAVersion = 2026.1.0` ;
- canal `stable`.

La compatibilité NVDA 2019.3 n’est plus promise : le minimum déclaré a été
resserré à NVDA 2026.1.0, version visée par le code actuel. La valeur
`lastTestedNVDAVersion = 2026.1.0` doit néanmoins être confirmée par un test
sur NVDA réel avant publication.

### 16. Chaîne d’installation clarifiée

[instAccesso.py](globalPlugins/instAccesso.py) est désormais explicitement documenté comme
un raccourci qui ouvre l’installateur officiel de NVDA, et non l’installation de
l’extension Accessolutions NVDA Pro. Le déclenchement automatique dépendant du
chemin du fichier a été supprimé, le geste est décrit par `@script` et les
erreurs d’ouverture sont journalisées puis annoncées à l’utilisateur.

### 17. Pipeline de publication renforcé

[build_release.yml](.github/workflows/build_release.yml) exécute maintenant une
validation AST avec contrôle minimal des exceptions nues, les tests unitaires
de l’updater et une vérification du contenu, du manifeste et de la version du
paquet final. Les actions GitHub sont verrouillées par empreinte de commit.

Aucune signature cryptographique de paquet n’est générée : elle nécessite une
clé privée de publication gérée par le projet. Le SHA-256 reste publié comme
contrôle d’intégrité.

## Régressions liées aux dernières modifications

Les incohérences initialement relevées dans le flux d’assistance ont été
corrigées : saisie interactive de la clé, encodage de l’URL, suppression de la
clé fixe, suppression de l’ancienne page HTML et mise à jour de la
documentation. La présence du gestionnaire `nvdaremote://` reste dépendante de
NVDA Remote et doit être vérifiée par un test réel.

Les validations restant à effectuer sont notamment celles de la recherche
incrémentale, du menu, des gestes et de l’installateur avec NVDA réel.

## Limites toujours présentes

- compatibilité NVDA+F7 à valider uniquement si une version ancienne doit être
  de nouveau prise en charge ;
- plusieurs usages d’APIs privées ou anciennes de NVDA, notamment la capture
  temporaire de clavier de la recherche incrémentale ;
- absence de signature cryptographique vérifiée par l’updater ;
- tests fonctionnels NVDA réels non exécutés dans cet environnement.

## Plan de correction recommandé

1. Tester le flux d’assistance avec NVDA Remote et une clé de test non sensible.
2. Tester le dialogue d’installation officiel avec une installation réelle de NVDA.
3. Tester le geste de journalisation avec NVDA réel, notamment avec un niveau
  forcé par la ligne de commande.
4. Valider la recherche incrémentale avec NVDA réel dans plusieurs navigateurs.
5. Valider le routage braille du Bloc-notes et la restauration OpenBook avec NVDA réel.
6. Tester `NVDA+F7` uniquement sur les anciennes versions encore ciblées.
7. Tester les gestes optionnels avec une carte utilisateur et les autres extensions.
8. Confirmer `lastTestedNVDAVersion` après un test réel sur la version concernée.
9. Mettre en place une signature cryptographique si le projet dispose d’une
  clé de publication et souhaite garantir l’authenticité de l’éditeur.

## Sources NVDA consultées

- [inputCore.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/inputCore.py) : capture des gestes et chargement des cartes de gestes.
- [addonHandler/__init__.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/addonHandler/__init__.py) : `AddonBundle`, installation, suppression différée et manifeste.
- [versionInfo.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/versionInfo.py) : variables de version actuelles et absence de `isTestVersion`.
- [browseMode.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/browseMode.py) : API des intercepteurs de documents et attributs privés.
- [gui/installerGui.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/gui/installerGui.py) : signature actuelle de `doInstall()`.
- [logHandler.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/logHandler.py) : niveaux et application de la journalisation NVDA.
- [config/configSpec.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/config/configSpec.py) : définition du niveau de journalisation configuré.
- [core.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/core.py) : `postNvdaStartup`, `callLater()` et cycle d’arrêt de NVDA.
- [globalPluginHandler.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/globalPluginHandler.py) : cycle de vie des global plugins.
- [appModuleHandler.py](https://raw.githubusercontent.com/nvaccess/nvda/master/source/appModuleHandler.py) : événements des app modules.

## Conclusion

L’updater, le cycle de vie, les chaînes localisables, les gestes optionnels,
l’installateur et le pipeline de publication ont été renforcés à partir du
point 10. Les contrôles automatiques sont maintenant exécutés dans le workflow.
Les validations fonctionnelles avec NVDA réel et, le cas échéant, la signature
cryptographique de publication restent à organiser.
