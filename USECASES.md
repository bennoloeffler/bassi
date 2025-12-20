# Tools and UseCases

- web search / deepsearch (just like google/openai) 
  BEISPIELE: 
  - welche Anbieter in der Nähe von Stuttgart lackieren Autoteile im Sinne einer Reperatur?
  - Was sind die Wettbewerber der Firma amf in Fellbach? Welche Produkte oder Preise sind insbesondere betroffen?

- local RAG for knowledge integration
  - Was weisst Du zum Thema Schutzraum? - suche in mcp rag-leann vunds-know-how

- browser automation (clicking)
  BEISPIELE
  - gehe zu v-und-s.de und suche die Namen des Teams. 
  

- bash (eg searching for files, compressing images)
  BEISPIELE:
  - nimm alle bilder in Folder XYZ und komprimiere sie auf max 20kb. Nenne sie <orig_name>_compressed.<orig_prefix>
  - suche im Subfolder XYZ rekursiv nach den 10 größsten Bildern, kopiere sie in den neuen Folder ~/riesen_bilder und mache eine Collage aus den Bildern und mache diese Schwarz-Weiss - in verschiedenen helligkeits und kontraststufen.



- database raw access (sql creation)
  BEISPIELE
  - zeige mir die Struktur der Datenbank.
  - füge diese email in die Datenbank crm-db ein: ...

- python creation for automation
  BEISPIELE:
  - schreibe ein script, das ...

- ms365 for all emails/calendar/sharepoint
  BEISPIELE:
  - lies meine emails von heute und gib mir eine Zusmamanfassung aller dingenden TODOs, die sich daraus ergeben.


- MIXED BEISPIELE
    
    - gehe zu website linkedIn (ich bin eingelogged), suche Kirsten Mayer bei der Firma V&S und schreibe ihr, dass mich gerne kommende Woche zum Thema Transformation austauschen will - schaue im meine Calendar und mache drei Terminvorschläge, 15 min.

    - lies meine Emails von heute und trage alle Vertriebs-Relevanten Ereignisse/Adressen/Firmen in die crm-db ein. Zusammenfassung bitte.
    
    - Zeige mir alle geplanten Vertriebs-Aktivitäten für diese Woche, schaue in meinen Kalender und trage mir die wichtigsten als Erinnerung oder Termin ein.
    
    - mache aus diesen drei Dateien a, b, c ein Gesamtkonzept G und speichere das. Schau Dir diese Angebote an und leite daraus und und G ein Angebot für die Herrn XY, Firma Z - Daten siehe crm-db
    
    - Zeige mir alle Vorgänge zum Kunden XYZ im letzten Jahr. Gibt es Anlass zur Sorge? Hat sich die Kommunikation verändert? Falls ja: Zeige mir Beispiele.

    - was sagt Urs Herding über V&S - suche in dem Folder: /Users/benno/VundS Dropbox/Externe Dateifreigabe/know-how-für-Berater


## an agent on itself ???
read emails of yesterday and today - maybe in junks of 10 if there are much more than 10, classify them in those categories and then "treat them the right way":
- spam - may be moved to folder 'Junk-Email'

- sales-relevant - those that needs to be treated in crm, including chances, todos, etc. extract the data and also move the complete email including documents to the CRM. AND: Create todos if needed. Then move to folder done-sales  

- time-window - those, where people are asking for online or offline time with me. Make a suggestion based on my calendar. Create a calendar-entry. In case of traveling, write an email to ANNA for bookings. For the moment estimate traveling time with mcp google maps and block time in Calendar. Then move to folder done-book-meeting.

- just-answer - those that needs just an anser no other todo. Write an answer in Benno-Style, if you can, and move it to folder Drafts. Then move to folder done-answer. 

- todo - may be marked as unread and should. Stay in Inbox. Estimate the time for the TODO and create a time window if its more than 15 minutes.

