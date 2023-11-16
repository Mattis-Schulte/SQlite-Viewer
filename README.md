# Dokumentation
## Gruppenmitglieder
- Mattis Schulte: Programmierung, Fehlerbehebung, Dokumentation
- Marvin Hillmann: Programmierung, Fehlerbehebung
- (Enno Rockmann): Dokumentation
## Zeitplanung
- 05.10.2023 Grundprogrammierung
- 02.11.2023 Fehlerbehebung
- 16.11.2023 Dokumentation und Abgabe
## 1. Zielsetzung (Selbstformuliert)
Das Ziel dieses Projekts ist die Entwicklung eines SQLite-Viewers, der Benutzern das Anzeigen und Sortieren von Datenbanktabellen in einem übersichtlichen Listcontrol ermöglicht. Die Hauptmerkmale des Listcontrols sollen wie folgt ausgestaltet sein:

- **Darstellung:** Die Spalten des Listcontrols sollen den Spaltennamen und Datentypen der ausgewählten Tabelle entsprechen.
- **Sortierung:** Der Benutzer soll die Möglichkeit haben, die Daten nach jeder Spalte auf- oder absteigend zu sortieren, indem er auf den Spaltenkopf klickt. Die Sortierreihenfolge soll durch ein Symbol im Spaltenkopf angezeigt werden.
- **Pagination (Seitennummern):** Um die Benutzerfreundlichkeit und Leistung zu verbessern, besonders wenn es um große Datensätze geht, sollte der Viewer eine Paginierungsfunktion unterstützen. Das bedeutet, dass die Datensätze in mehrere Seiten aufgeteilt werden und der Benutzer kann durch die Seiten navigieren, um die Daten anzuzeigen. Dies erfordert:
    - Bedienelemente für das schnelle Navigieren zur nächsten oder vorherigen Seite.
    - Anzeige der aktuellen Seitenposition, zum Beispiel "Seite X von Y".
    - Speichern der aktuellen Sortiereinstellungen sowie der Spaltenbreite und -anordnung beim Seitenwechsel.
- **Variable Seitengröße**: Der Benutzer soll aus einem Menü auswählen können, wie viele Einträge pro Seite im Listcontrol angezeigt werden sollen. Diese Flexibilität ermöglicht es dem Benutzer, das Datenansichtserlebnis zu personalisieren und zu optimieren. Hierfür wird ein Einstellungsmenü oder ein Dropdown, das verschiedene Optionen für Seitenzahlen anbietet (z.B. 10, 25, 50, 100).
## 2. Arbeitsgestaltung
Da wir die selbst gesteckten sowie die vorgegebenen Ziele relativ schnell erreicht haben, waren wir in der Lage, unser Programm um zusätzliche Funktionen zu erweitern. Diese Erweiterungen beinhalten eine verbesserte Menüstruktur, eine vereinfachte Suchfunktion sowie verschiedene Tools zur Datenanalyse. Den gruppeninternen Austausch und die Koordination des Projektes haben wir effektiv über GitHub gestaltet. Die Plattform ermöglichte es uns, Code zu teilen, gemeinsam an Dokumenten zu arbeiten und über Issues und Pull Requests stetig in Kommunikation zu bleiben. So konnten wir eine hohe Transparenz in der Entwicklung schaffen und zugleich sicherstellen, dass alle Teammitglieder stets über den aktuellen Stand des Projekts informiert waren.
## 3. Probleme
Die Implementierung von Threading erwies sich als wesentlich, um das Einfrieren der wxPython-Benutzeroberfläche beim Laden großer Datenmengen zu verhindern. Diese Notwendigkeit brachte jedoch einen erhöhten Entwicklungsaufwand mit sich und führte zu Herausforderungen bei der Gewährleistung einer reibungslosen Ausführung. Insbesondere stellten wir fest, dass Race Conditions, also Konflikte zwischen gleichzeitig ausgeführten Prozessen, auftraten, die aufgrund ihrer Natur schwierig zu bewältigen waren. Trotz unserer Bemühungen konnten wir diese Probleme nicht vollständig lösen, was die Stabilität und Zuverlässigkeit unserer Anwendung beeinträchtigte.
## 4. Beschreibung der Lösung
In unserem Projekt nutzten wir Pandas, um einen flexiblen SQLite-Viewer zu erstellen, der auch CSV- und Excel-Tabellen verarbeiten kann. Diese Herangehensweise ermöglichte es uns, Daten unterschiedlicher Formate zu handhaben und bereitzustellen, ohne zusätzlichen Implementierungsaufwand zu betreiben.

Mit der Kombination aus Pandas, SciPy und Matplotlib erweiterten wir die Funktionalität unseres Viewers um Datenanalyse- und Visualisierungstools. Benutzer konnten daher innerhalb der Anwendung einfache Datenanalysen durchführen und ihre Daten in Form von Diagrammen visualisieren, was den SQLite-Viewer zu einem vielseitigen Werkzeug für Datenanalyse und Visualisierung machte. Trotz technischer Herausforderungen, insbesondere beim Threading, lieferte das Projekt erfolgreich ein nützliches Tool für die Verarbeitung und Analyse von Daten.
## 5. Fazit
Das Projekt zur Entwicklung eines SQLite-Viewers hat zu einem multifunktionalen Tool geführt, das Funktionen zur Datenanzeige, -sortierung, -suche, -analyse und -visualisierung bietet. Durch die Verwendung von Pandas und anderen Bibliotheken wurde eine benutzerfreundliche Anwendung geschaffen, die auch große Datenmengen effektiv handhaben kann. Obwohl die Einführung von Threading technische Herausforderungen mit sich brachte, hat die kollaborative Entwicklung über GitHub erheblich zum Gelingen des Projekts beigetragen.

Insgesamt wurde das ursprüngliche Ziel erreicht und durch zusätzliche Features erweitert. Das Ergebnis ist ein leistungsfähiges Tool für Datenverarbeitungs- und Analyseaufgaben, das trotz einiger Stabilitätsprobleme eine wertvolle Ressource für Benutzer darstellt.